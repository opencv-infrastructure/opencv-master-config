from twisted.internet import defer
from factory_ocl import OCL_factory as ParentClass

class ValgrindFactory(ParentClass):
    def __init__(self, **kwargs):
        useSlave = ['linux-1']
        kwargs['useSlave'] = kwargs.pop('useSlave', useSlave)
        kwargs['dockerImage'] = kwargs.pop('dockerImage', (None, 'valgrind'))
        ParentClass.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def initialize(self):
        self.setProperty('parallel_tests', 1)
        yield ParentClass.initialize(self)

    def getRunPy(self, full = False):
        r = ParentClass.getRunPy(self, full)
        if full:
            r.append("--valgrind")
            r.append("--valgrind_supp=../%s/platforms/scripts/valgrind.supp" % self.SRC_OPENCV)
        return r

    def getTestBlacklist(self, isPerf=False):
        return ParentClass.getTestBlacklist(self, isPerf) + ["videoio", "java", "python", "python2", "python3"]

    def getTestMaxTime(self, isPerf):
        return 240 * 60

    def getTestTimeout(self):
        return 40 * 60

