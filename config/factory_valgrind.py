from twisted.internet import defer

from build_utils import isBranch24
from factory_ocl import OCL_factory as ParentClass

class ValgrindFactory(ParentClass):
    def __init__(self, **kwargs):
        useSlave = ['linux-2']
        cmake_parameters = kwargs.pop('cmake_parameters', {})
        cmake_parameters['CMAKE_CXX_FLAGS'] = '-g -O1'
        cmake_parameters['CPU_DISPATCH'] = ''
        cmake_parameters['CPU_BASELINE'] = 'AVX'
        cmake_parameters['ENABLE_PRECOMPILED_HEADERS'] = 'OFF'
        cmake_parameters['WITH_IPP'] = 'OFF'
        cmake_parameters['OPENCV_ENABLE_MEMORY_SANITIZER'] = 'ON'
        kwargs['cmake_parameters'] = cmake_parameters
        kwargs['useSlave'] = kwargs.pop('useSlave', useSlave)
        kwargs['dockerImage'] = kwargs.pop('dockerImage', (None, 'valgrind'))
        kwargs['testXML'] = True
        # changes builder name: kwargs['useIPP'] = False
        ParentClass.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def initialize(self):
        self.setProperty('parallel_tests', 2)
        yield ParentClass.initialize(self)

    def getRunPy(self, full = False):
        r = ParentClass.getRunPy(self, full)
        if full:
            r += ([
                "--valgrind",
                "--valgrind_supp=../%s/platforms/scripts/valgrind.supp" % self.SRC_OPENCV,
            ] if isBranch24(self) else [
                "--valgrind",
                "--valgrind_opt=--tool=memcheck",
                "--valgrind_opt=--leak-check=full",
                "--valgrind_opt=--show-reachable=yes",
                "--valgrind_opt=--undef-value-errors=yes",
                "--valgrind_opt=--track-origins=yes",
                "--valgrind_opt=--child-silent-after-fork=no",
                "--valgrind_opt=--trace-children=yes",
                "--valgrind_opt=--gen-suppressions=all",
                "--valgrind_opt=-v",
                "--valgrind_supp=../%s/platforms/scripts/valgrind.supp" % self.SRC_OPENCV,
                "--valgrind_supp=../%s/platforms/scripts/valgrind_3rdparty.supp" % self.SRC_OPENCV,
            ])
        return r

    def getTestBlacklist(self, isPerf=False):
        return ParentClass.getTestBlacklist(self, isPerf) + ["java", "python", "python2", "python3"]

    def getTestMaxTime(self, isPerf):
        return 240 * 60

    def getTestTimeout(self):
        return 40 * 60

