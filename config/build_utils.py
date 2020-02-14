from twisted.internet import defer

from buildbot.process.properties import Interpolate
from buildbot.status.results import SUCCESS, WARNINGS, FAILURE, EXCEPTION, RETRY, SKIPPED
from buildbot.steps.shell import ShellCommand, SetPropertyFromCommand


class OSType():
    WINDOWS = 'Win'
    LINUX = 'Lin'
    MACOSX = 'Mac'
    ANDROID = 'Android'

    all = [WINDOWS, LINUX, MACOSX, ANDROID]

    suffix = {
        WINDOWS:'win',
        LINUX:'lin',
        MACOSX:'mac',
        ANDROID:'android'
    }
    build_suffix = suffix

class WinCompiler:
    VC10 = 'vc10' # Visual Studio 2010
    VC11 = 'vc11' # Visual Studio 2012
    VC12 = 'vc12' # Visual Studio 2013
    VC14 = 'vc14' # Visual Studio 2015
    VC15 = 'vc15' # Visual Studio 2017
    VC16 = 'vc16' # Visual Studio 2019

    @staticmethod
    def getCMakeOptions(compiler, platform, is64):
        platform = platform if platform else ('x64' if is64 else 'Win32')
        if platform == 'x86':
            platform = 'Win32'

        if compiler == WinCompiler.VC16:
            return ('Visual Studio 16 2019', (None, platform))
        elif compiler == WinCompiler.VC15:
            return ('Visual Studio 15 2017', (None, platform))

        if platform == 'x64':
            platform = 'Win64'
        platform = '' if platform == 'Win32' else (' ' + platform)
        cmake_generator = None
        if compiler == WinCompiler.VC10:
            cmake_generator = 'Visual Studio 10' + platform
        elif compiler == WinCompiler.VC11:
            cmake_generator = 'Visual Studio 11' + platform
        elif compiler == WinCompiler.VC12:
            cmake_generator = 'Visual Studio 12' + platform
        elif compiler == WinCompiler.VC14:
            cmake_generator = 'Visual Studio 14' + platform
        return (cmake_generator, None)

def getDocPackScript(osType):
    # on worker
    if osType == OSType.LINUX:
        return "/app/scripts/pack_docs.py"
    elif osType == OSType.MACOSX:
        return "/opt/build/scripts/pack_docs.py"

def getDocUploadScript():
    # on master
    return '/app/scripts/docs_upload.sh'

def getUploadPathTemplate():
    return 'opencv_releases/%(prop:buildername)s/%(prop:timestamp)s--%(prop:buildnumber)s'

@defer.inlineCallbacks
def interpolateParameter(value, props):
    if hasattr(value, 'getRenderingFor'):
        value = yield defer.maybeDeferred(value.getRenderingFor, props)
    defer.returnValue(value)

def getDropRoot(masterPath=True):
    return '' if not masterPath else '/data/artifacts/'

def getExportURL():
    return 'export/'

def getExportDirectory():
    return getDropRoot() + 'export/'

def _getMergeNeededFn(codebase):
    def mergeNeeded(step):
        ss = step.build.getSourceStamp('%s_merge' % codebase)
        return (ss is not None) and (ss.repository != '')
    return mergeNeeded

def getMergeCommand(codebase, workdir, doStepIf=True):
    def doStepIfFn(step):
        if doStepIf == False or (not doStepIf == True and not doStepIf(step)):
            return False
        return _getMergeNeededFn(codebase)(step)
    return ShellCommand(name="Merge %s with test branch" % codebase, haltOnFailure=True,
                        command=Interpolate('git pull -v "%%(src:%s_merge:repository)s" "%%(src:%s_merge:branch)s"' % (codebase, codebase)),
                        workdir=workdir, description="merge %s" % codebase, descriptionDone="merge %s" % codebase,
                        doStepIf=doStepIfFn);

def isBranch24(self):
    return self.getProperty('branch', default='master').startswith("2.4")

def isNotBranch24(self):
    return not isBranch24(self)

def isBranch34(self):
    return self.getProperty('branch', default='master').startswith("3.4")

def isNotBranch34(self):
    return not isBranch34(self)

def isBranchMaster(self):
    return not isBranch24(self) and not isBranch34(self)

def valueToBool(v):
    return v in ['ON', '1', 'TRUE', 'True', True, 1]

def hideStepIfFn(result, s):
    return result not in [SUCCESS, WARNINGS, FAILURE, EXCEPTION, RETRY]

hideStepIfDefault = hideStepIfFn

def hideStepIfSuccessSkipFn(result, s):
    return result in [SUCCESS, SKIPPED]
