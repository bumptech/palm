import sys
import os
import traceback
from optparse import OptionParser

from palm.palmc.codegen import gen_module, convert_proto_name
from palm.palmc.parse import make_parser, ProtoParseError, Package

class Namespace(object):
    def __init__(self, package, file):
        self.file = file
        self.package = package

    def __str__(self):
        return "(Namespace) {0} - {1}".format(str(self.package), str(self.file))

    def __repr__(self):
        return str(self)

def run():
    usage = "usage: %prog source dest [options]"

    parser = OptionParser()
    parser.add_option("-s", "--with-slots",
                      dest="with_slots",
                      action="store_true",
                      help="generate code using __slots__")
    (options, args) = parser.parse_args()

    if len(args) != 2:
        parser.error("exactly two arguments required: path to directory with .proto files and path to destination package")

    d = args[0]
    od = args[1]
    exit_status = 0
    packages_to_files = {}
    files_to_packages = {}
    parsed = []
    protos = [f for f in os.listdir(d) if f.endswith(".proto")]

    try:
        print("Parsing...")
        for proto_file in protos:
            sys.stdout.write(("%s..." % proto_file).ljust(70))
            sys.stdout.flush()

            source = open(os.path.join(d, proto_file)).read()
            _, res, l = make_parser().parse(source)

            if l != len(source):
                raise Exception("Syntax error on line %s near %r" % (
                    source[:l].count('\n') + 1,
                    source[l:l+10]))

            package_list = [m for m in res if type(m) is Package]
            if len(package_list) == 1:
                package = package_list[0].name
                ns = Namespace(package, proto_file)
                packages_to_files[package] = ns
                files_to_packages[proto_file] = ns
            elif len(package_list) > 1:
                raise Exception("Proto file %s declares more than 1 package." % proto_file)
            else:
                package = None

            parsed.append((res, package, proto_file))
            sys.stdout.write("[OKAY]\n")

        print("Generating code...")
        for (res, package, proto_file) in parsed:
            sys.stdout.write(("%s..." % proto_file).ljust(70))
            sys.stdout.flush()
            # Filter the package mappings given to
            # gen_module based on the packages
            # imported by this proto file.
            #
            # Fortunately, imports are not transitive (except 'import public'
            # but we aren't going to worry abou that), so we only need
            # to look for packages imported directly.
            imports = [m for m in res if type(m) is str]
            module_packages = dict([(p, ns) for (p, ns)
                                   in packages_to_files.iteritems()
                                   if ns.file in imports])
            s = gen_module([m for m in res if type(m) is tuple],
                    imports,
                    [m for m in res if type(m) is list],
                    options.with_slots,
                    module_packages,
                    package
                    )
            open(os.path.join(od, convert_proto_name(proto_file) + ".py"), 'wb').write(s)
            sys.stdout.write("[OKAY]\n")
    except:
        sys.stdout.write("[FAIL]\n")
        traceback.print_exc()
        exit_status = 1

    sys.stdout.flush()
    return exit_status
