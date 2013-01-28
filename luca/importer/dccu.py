"""Delta Community Credit Union PDF statements."""

import re
import subprocess
import luca.files
from datetime import date
from luca.model import Transaction


debug = False
date_re = re.compile(r'\d\d/\d\d$')
amount_re = re.compile(r'[\d,]+\.\d\d-?$')


def matches(content):
    return True  # TODO: put real check here


def parse(filename):

    command = ['pdftotext', '-layout', filename, '-']
    content = subprocess.check_output(command)

    config = luca.files.parse_ini()

    if config.has_option('import', 'replace'):
        for line in config.get('import', 'replace').splitlines():
            line = line.strip()
            if not line:
                continue
            pattern, replacement = line.split('|')
            content = content.replace(pattern, replacement)

    words = content.split()
    starts = [ i for i in range(len(words) - 1)
               if words[i] == 'Balance' and words[i+1] == 'Forward' ]

    transactions = []

    for start in starts:
        section = words[start:]

        n = start
        while words[n] != 'ID':
            n -= 1
        account_name = ' '.join(words[n+1:start])

        end = 0
        while True:
            if section[end] == 'Ending' and section[end+1] == 'Balance':
                end += 3
                break
            if section[end] == 'Closed' and section[end+1] == 'THIS':
                break
            end += 1

        del section[end:]
        if debug:
            print 'SECTION {}:\n{}'.format(account_name, section)

        # The `section` word list is now established.

        year = 2012

        dates = [ i for i in range(len(section) - 1)
                  if date_re.match(section[i])
                  and not (i > 0 and date_re.match(section[i-1])) ]

        for m in range(len(dates) - 1):
            i, j = dates[m], dates[m+1]
            trans = section[i:j]
            if debug:
                print 'TRANSACTION:\n', trans

            amount_indexes = [
                k for k in range(len(trans) - 1)
                if amount_re.match(trans[k]) and amount_re.match(trans[k+1])
                ]

            if len(amount_indexes) == 0 and trans[1] == 'INQ':
                continue

            if not amount_indexes:
                # TODO: billpayer check
                continue

            k = amount_indexes[0]

            description_words = trans[1:k]
            if date_re.match(description_words[0]):
                effective_date = date(year, *[
                    int(word) for word in description_words.pop(0).split('/')
                    ])
            else:
                effective_date = None

            amount = trans[k]
            if amount.endswith('-'):
                amount = '-' + amount[:-1]

            month, day = [ int(s) for s in trans[0].split('/') ]

            t = Transaction(
                account_name=account_name,
                posted_date=date(year, month, day),
                effective_date=effective_date,
                description=' '.join(description_words),
                amount=amount,
                # at k+1 is the new balance
                comments=[' '.join(trans[k+2:])],
                )
            transactions.append(t)

        i = dates[-1]
        if section[i+1] == 'ID':
            pass # Closed
        else:
            assert section[i+1] == 'Ending'
            assert section[i+2] == 'Balance'

        # print 'end', section[i], section[i+3]

    return transactions