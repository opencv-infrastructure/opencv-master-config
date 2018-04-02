from buildbot import interfaces
from buildbot.config import BuilderConfig
from buildbot.process import builder
from buildbot.process.build import Build
from buildbot.process.buildrequest import BuildRequest
from buildbot.process.factory import BuildFactory
from buildbot.process.properties import PropertiesMixin

from twisted.internet import defer
from twisted.python import components

import copy

class _BuildStepDummyFactory():

    def __init__(self, step):
        self.step = step

    def buildStep(self):
        return self.step


class BuildFactoryWrapper(BuildFactory):

    def __init__(self, me):
        self.me_ = me
        BuildFactory.__init__(self);


    def newBuild(self, requests):
        clone = copy.copy(self.me_)
        clone.bb_requests = requests
        assert clone.factorySteps is None
        clone.factorySteps = []
        clone.onNewBuild()

        class BuildWrapper(Build):

            def __init__(self, *args, **kwargs):
                self.me_ = clone
                clone.bb_build = self
                Build.__init__(self, *args, **kwargs);


            def run(self):
                self.me_.steps = self.steps
                return self.me_.run_()


            def runCleanup(self):
                return self.me_.runCleanup()


        self.buildClass = BuildWrapper

        self.workdir = clone.workdir
        self.steps = []
        if clone.factorySteps:
            for step in clone.factorySteps:
                assert step._step_status is None, "Step was already used. Don\'t create steps during initConstants() call!"
                self.steps.append(_BuildStepDummyFactory(step))
        clone.factorySteps = None

        b = BuildFactory.newBuild(self, requests)
        return b



class BuilderNewStyle(object, PropertiesMixin):

    bb_requests = None  # list of buildbot.process.buildrequest.BuildRequest
    bb_build = None  #: :type bb_build: buildbot.process.Build

    workdir = '.'

    factorySteps = None  # old-style static steps

    def __code_completion_helper__(self):
        if __debug__:
            self.bb_requests = BuildRequest()
            self.bb_build = Build()

    def __init__(self, **kwargs):
        if not hasattr(self, 'builderName'):
            self.builderName = kwargs.pop('builderName', None)
        if not hasattr(self, 'useSlave'):
            self.useSlave = kwargs.pop('useSlave', None)
        if not hasattr(self, 'tags'):
            self.tags = list(kwargs.pop('tags', []))
        self.locks = kwargs.pop('locks', [])
        assert len(kwargs.keys()) == 0, 'Unknown parameters: ' + ' '.join(kwargs.keys())


    def onNewBuild(self):
        '''
        It is called for cloned self object.

        Current build properties can be found via self.bb_requests

        Here we can populate "static" set of build steps
        '''
        self.fillStaticSteps()
        pass


    @defer.inlineCallbacks
    def run_(self):
        yield self.runPrepare()
        yield self.run()
        pass


    @defer.inlineCallbacks
    def runPrepare(self):
        yield None
        pass


    @defer.inlineCallbacks
    def run(self):
        yield None
        pass


    @defer.inlineCallbacks
    def runCleanup(self):
        yield None
        pass


    def fillStaticSteps(self):
        pass


    def initConstants(self):
        pass


    def getName(self):
        if self.builderName:
            raise Exception('implement getName() method or pass "builderName" ctor parameter')
        return self.builderName


    def getSlaves(self):
        if self.useSlave is None:
            raise Exception('implement getSlaves() method or pass "useSlave" ctor parameter')
        return [self.useSlave] if isinstance(self.useSlave, str) else self.useSlave


    def getFactory(self):
        return BuildFactoryWrapper(self)


    def getFactoryProperties(self):
        props = {}
        return props

    def getTags(self):
        return self.tags

    def register(self):
        self.initConstants()
        return BuilderConfig(
            name=self.getName(),
            slavenames=self.getSlaves(),
            factory=self.getFactory(),
            mergeRequests=False,
            tags=list(set(self.getTags())),
            properties=self.getFactoryProperties(),
            canStartBuild = builder.enforceChosenSlave,
            locks=self.locks)

    #
    # Helpers
    #
    def addFactoryStep(self, step):
        assert self.bb_build is None, 'Build started, can\'t add factory step, use runtime step'
        self.factorySteps.append(step)


    def addStep(self, step, insertPosition=0, addToQueue=True):
        '''
        Add step into build.

        insertPosition=None - append
        insertPosition=0 - insert
        insertPosition=someStep - insert after specified step
        '''
        assert self.bb_build is not None, 'Build is not created, run this method only from run/runCleanup methods'
        return self.bb_build.addStep(step, insertPosition, addToQueue)


    def processStep(self, step):
        '''
        Process specified step

        It is Deferred call, use yield!

        Throws BuildFailed if step was failed (and build terminates)
        '''
        return self.bb_build.processStep(step)



components.registerAdapter(
    lambda _: interfaces.IProperties(_.bb_build),
    BuilderNewStyle, interfaces.IProperties)
