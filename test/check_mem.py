# NOTE Make sure that you regenerate your test_palm.py file by running
# palmc when testing memory efficiency improvements that impact the
# generated Python code.

# NOTE This script needs to be run inside the test/ directory in the
# palm repo.

import sys
import time

from test_palm import Test, Secret
from subprocess import Popen, PIPE

# Serialized Test object with required fields set.
sample_bytes = '\x90\x03\x01\x98\x03\x02\xa0\x03\x06'

def check(pid, run_type):
    ps = Popen('ps aux | grep %d | grep -v grep' % pid, shell=True, stdout=PIPE)
    raw = ps.communicate()[0].split(' ')
    stats = [f for f in raw if f]
    #     name      vsz       rss
    print run_type, stats[4], stats[5]

if len(sys.argv) == 1:
    # Test both baseline memory and 10k objects loaded into memory.
    for opt in ['baseline', 'normal-append', 'fast-append']:
        p = Popen(['python', sys.argv[0], opt])
        time.sleep(10)
        assert p.returncode is None
        check(p.pid, opt)
        p.terminate()
else:
    if sys.argv[1] == 'baseline':
        pass
    else:
        pb = Test(open('big-test-palm.dat').read())
        if sys.argv[1] == 'normal-append':
            pb.r_secret.append(Secret(code=0, message="normal-append"))
        elif sys.argv[1] == 'fast-append':
            pb.r_secret__fast_append(Secret(code=0, message="normal-append"))
        data = pb.dumps()
    try:
        raw_input()
    except:
        pass
