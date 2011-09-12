import sys
import os
import traceback

from palm.palmc.codegen import gen_module, convert_proto_name
from palm.palmc.parse import make_parser

def run():
    assert len(sys.argv) == 2, "exactly one argument required: path to directory with .proto files"
    d = sys.argv[1]

    protos = [f for f in os.listdir(d) if f.endswith(".proto")]

    for p in protos:
        sys.stdout.write(("%s..." % p).ljust(70))
        sys.stdout.flush()

        source = open(os.path.join(d, p)).read()

        try:
            parser = make_parser()
            r = parser.parse(source)


            res = r[1]
            s = gen_module([m for m in res if type(m) is tuple], [m for m in res if type(m) is str])
            open(os.path.join(d, convert_proto_name(p) + ".py"), 'wb').write(s)
        except:
            sys.stdout.write("[FAIL]\n")
            sys.stdout.flush()
            traceback.print_exc()
        else:
            sys.stdout.write("[OKAY]\n")
            sys.stdout.flush()
