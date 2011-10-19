import timeit
import time
import cProfile as profiler
from test_palm import Test as FTest
from test_pb2 import Test as STest
import sys

b = open('out.b').read()

def runpalm():
    t = time.time()
    for x in xrange(10000):
        FTest(b)
    print 'Palm, 10,000 decodes:', time.time() - t

    t = time.time()
    p = FTest(b)
    for x in xrange(10000):
        p.a = x
        p.dumps(update=True)
    print 'Palm, 10,000 encodes:', time.time() - t

if not sys.argv[1:] or 'prof' in sys.argv[1:] or 'palm' in sys.argv[1:]:
    if 'prof' in sys.argv[1:]:
        profiler.run('runpalm()')
        raise SystemExit(0)
    else:
        runpalm()

print ''
print '-' * 72
print ''

def runpb():
    t = time.time()
    for x in xrange(10000):
        STest().ParseFromString(b)
    print 'PB, 10,000 decodes:', time.time() - t

    t = time.time()
    p = STest()
    p.ParseFromString(b)

    for x in xrange(10000):
        p.a = x
        p.SerializeToString()
    print 'PB, 10,000 encodes:', time.time() - t

if not sys.argv[1:] or 'pb' in sys.argv[1:]:
    runpb()
