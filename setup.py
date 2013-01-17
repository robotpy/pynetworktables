
import os
import os.path
import sys
from distutils.core import setup, Extension

try:
    import sipdistutils
except ImportError:
    sys.stderr.write("ERROR: You must have SIP installed to build this extension\n")
    sys.stderr.write("-> http://www.riverbankcomputing.com/software/sip\n")
    exit(1)


    
if 'ROBOTPY' not in os.environ:
    sys.stderr.write("ERROR: You must specify the path to the RobotPy source via the ROBOTPY environment variable!\n")
    exit(1)
    
robotpy_path = os.environ['ROBOTPY']

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
                   os.path.join(src_dir, 'System.cpp'),
                   os.path.join(src_dir, 'Task.cpp')]


# don't want to bother with these for now.. too many interdependencies
exclude_dirs = ['Buttons', 'Commands', 'LiveWindow']
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

    def initialize_options(self):
        sipdistutils.build_ext.initialize_options(self)
        self.sip_opts = '-g -e -I "%s" -I "%s"' % (sip_dir, sip_base)
        
    def build_extensions(self):
        if self.compiler.compiler_type == 'msvc':
            for e in self.extensions:
                e.extra_compile_args += ['/DWIN32', '/EHsc'] #, '/Od']
                
        elif self.compiler.compiler_type == 'mingw32':
            for e in self.extensions:
                e.extra_compile_args += ['-DWIN32']
        
        sipdistutils.build_ext.build_extensions(self)

# setup stuff for extension
source_files = extra_src_files + cpp_files
include_dirs = [src_dir, sip_dir, wpilib_base, cpp_base]
libraries = None

if sys.platform == 'win32':
    libraries = ['ws2_32']


setup(
    name = 'pynetworktables',
    version = '1.0',
    ext_modules=[
    Extension("pynetworktables", source_files, include_dirs=include_dirs, libraries=libraries),
    ],

    cmdclass = {'build_ext': custom_build_ext}
)


