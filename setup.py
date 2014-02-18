__version__ = '2014.2'

import os
import os.path
import platform
import sys
from distutils.core import setup, Extension
from distutils.command.install_lib import install_lib

try:
    import sipdistutils
except ImportError:
    sys.stderr.write("ERROR: You must have SIP installed to build this extension\n")
    sys.stderr.write("-> http://www.riverbankcomputing.com/software/sip\n")
    exit(1)


    
if 'ROBOTPY' not in os.environ:
    sys.stderr.write("ERROR: You must specify the path to the RobotPy source via the ROBOTPY environment variable!\n")
    exit(1)
    
robotpy_path = os.path.abspath(os.environ['ROBOTPY'])

# check that it's actually valid
wpilib_base = os.path.join(robotpy_path, 'Packages', 'wpilib')

if not os.path.isdir(wpilib_base):
    sys.stderr.write("ERROR: WPILib files were not detected at '%s'\n" % wpilib_base)
    exit(1)


root = os.path.split(os.path.abspath(__file__))[0]
src_dir = os.path.join(root, 'src')
sip_dir = os.path.join(root, 'sip')
    
# iterate over the RobotPy directories, add sip/matching wpilib files to it
cpp_base = os.path.join(wpilib_base, 'WPILib')
sip_base = os.path.join(wpilib_base, 'sip')

cpp_files = []
extra_src_files = [os.path.join(sip_dir, 'module.sip'),
                   os.path.join(src_dir, 'DefaultThreadManager.cpp'),
                   os.path.join(src_dir, 'ErrorBase.cpp'),
                   os.path.join(src_dir, 'Scheduler.cpp'),
                   os.path.join(src_dir, 'System.cpp'),
                   os.path.join(src_dir, 'OSAL', 'Task.cpp')]


# don't want to bother with these for now.. too many interdependencies
exclude_dirs = ['Buttons', 'Commands']
exclude_files = [
    'networktables2/thread/DefaultThreadManger.cpp',
    'networktables2/util/System.cpp'
]

exclude_dirs = list(map(os.path.normpath, exclude_dirs))
exclude_files = list(map(os.path.normpath, exclude_files))

# this is done stupidly because of spelling mistakes in wpilib... 
for i, (dirpath, dirnames, filenames) in enumerate(os.walk(sip_base)):
    if i == 0:
        continue
        
    dname = dirpath[len(sip_base)+1:]
    if dname in exclude_dirs:
        continue
        
    cpppath = os.path.join(cpp_base, dname)
        
    for fname in os.listdir(cpppath):
        if fname[-4:] != '.cpp':
            continue    
        
        if os.path.join(dname, fname) in exclude_files:
            continue
        
        cpp_fname = os.path.join(cpppath, fname)
        cpp_files.append(cpp_fname)

class custom_build_ext(sipdistutils.build_ext):

    def finalize_options(self):
        sipdistutils.build_ext.finalize_options(self)
        self.sip_opts += ['-g', '-e', '-I', sip_dir, '-I', sip_base]
        
    def build_extensions(self):
    
        if self.compiler.compiler_type == 'msvc':
            for e in self.extensions:
                e.include_dirs += [os.path.join(src_dir, 'msvc')]
                e.extra_compile_args += ['/DWIN32', '/EHsc']
                
        elif self.compiler.compiler_type == 'mingw32':
            for e in self.extensions:
                e.extra_compile_args += ['-DWIN32']
                
            # see http://bugs.python.org/issue12641
            if 'NO_MINGW_HACK' not in os.environ:
                keys = ['compiler', 'compiler_so', 'compiler_cxx', 'linker_exe', 'linker_so']
                for key in keys:
                    attr = getattr(self.compiler, key)
                    if '-mno-cygwin' in attr:
                        del attr[attr.index('-mno-cygwin')]
        
        sipdistutils.build_ext.build_extensions(self)


# if PYNET_INCLUDE_SIP is in the environment, then include SIP
# -> This is intended for building windows installers, so we can include
#    sip as a dependency. SIP must have been built with --sip-module=pynetworktables_sip,
#    otherwise this will fail
class custom_install(install_lib):
    if 'PYNET_INCLUDE_SIP' in os.environ and str(os.environ['PYNET_INCLUDE_SIP']) == "1":
        def install(self):
            # copy the custom sip module to the build directory so it gets
            # picked up by the bdist_wininst :)
            import pynetworktables_sip
            self.copy_file(pynetworktables_sip.__file__, self.build_dir)
            return install_lib.install(self)


# setup stuff for extension
source_files = extra_src_files + cpp_files
include_dirs = [src_dir, sip_dir, wpilib_base, cpp_base]
libraries = None
define_macros = [("PYNETWORKTABLES_VERSION", '"%s"' % __version__)]
extra_compile_args = None
extra_link_args = None


if sys.platform == 'win32':
    libraries = ['ws2_32']

    # Generate pdb files for debugging on msvc only
    if 'PYNET_DEBUG' in os.environ and str(os.environ['PYNET_DEBUG']) == "1":
        # TODO: figure out output directory name
        
        major, minor = platform.python_version_tuple()[:2]
        
        pdb_file = os.path.join(os.path.dirname(__file__), "pynetworktables-%s%s.pdb" % (major, minor))
        extra_link_args = ['/DEBUG', '/PDB:"%s"' % pdb_file]
        extra_compile_args = ['/Zi', '/Od']

setup(
    name = 'pynetworktables',
    version = __version__,
    ext_modules=[
        Extension("pynetworktables", source_files,
                  define_macros=define_macros,
                  include_dirs=include_dirs,
                  libraries=libraries,
                  extra_compile_args=extra_compile_args,
                  extra_link_args=extra_link_args),
    ],

    cmdclass = {'build_ext': custom_build_ext,
                'install_lib': custom_install }
)


