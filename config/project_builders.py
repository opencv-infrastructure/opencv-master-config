import os
from build_utils import OSType
from build_utils import WinCompiler

print "Configure builds..."

import constants
from constants import trace, PLATFORM_ANY, PLATFORM_DEFAULT, PLATFORM_SKYLAKE_X

import buildbot_passwords
from buildbot.buildslave import BuildSlave

INTEL_COMPILER_TOOLSET_CURRENT=('-icc17', '"Intel C++ Compiler 17.0"')
INTEL_COMPILER_DOCKER_CURRENT=('-icc17', 'ubuntu-icc:16.04')

workers = []
for worker in constants.worker:
    trace("Register worker: " + worker + " with passwd=*** and params=(%s)" % constants.worker[worker])
    workers.append(BuildSlave(worker, buildbot_passwords.worker[worker], **(constants.worker[worker])))

platforms = [
    PLATFORM_DEFAULT,
    PLATFORM_SKYLAKE_X,
]

def platformParameter(branch, **params):
    isContrib = params.get('isContrib', None)
    if branch == '2.4' or isContrib:
        return [PLATFORM_DEFAULT]
    return platforms

PlatformWindowsCompiler = {
    PLATFORM_DEFAULT: [WinCompiler.VC14], #, WinCompiler.VC15],
}

def osTypeParameter(platform, **params):
    if platform == PLATFORM_DEFAULT:
        return OSType.all
    if platform == PLATFORM_SKYLAKE_X:
        return [OSType.LINUX]
    assert False

def androidABIParameter(platform, osType, **params):
    if osType != OSType.ANDROID:
        return [None]
    if platform in ['xxxxx']:
        return [None, 'x86']
    return [None]

def androidDeviceParameter(platform, osType, **params):
    if osType != OSType.ANDROID:
        return [None]
    if platform in ['xxxxx']:
        return ['xxxxx.android:5555']
    else:
        return [None]

def androidParameters():
    return [dict(androidABI=androidABIParameter), dict(androidDevice=androidDeviceParameter)]

def is64ParameterCheck(platform, osType, **params):
    if osType == OSType.ANDROID:
        return [None]
    if platform == PLATFORM_SKYLAKE_X:
        return [True]
    if platform in ['xxxxx']:
        return [False]
    if osType == OSType.WINDOWS:
        return [True, False]
    if osType == OSType.LINUX:
        return [True, False]
    if osType == OSType.MACOSX:
        return [None]
    return [True]

def availableCompilers(platform, osType, **params):
    if osType == OSType.ANDROID:
        return [None]
    if osType == OSType.WINDOWS:
        return PlatformWindowsCompiler[platform]
    else:
        return [None]

def availableToolset(platform, osType, **params):
    if osType == OSType.WINDOWS:
        return [None] #, INTEL_COMPILER_TOOLSET_CURRENT]
    else:
        return [None]

def useIPPParameter(branch, platform, osType, compiler, **params):
    androidABI = params.get('androidABI', None)
    if androidABI == 'x86':
        res = [False, 'ICV']
    elif osType == OSType.ANDROID:
        return [None]
    elif osType == OSType.MACOSX:
        res = [False, 'ICV']
    elif osType == OSType.WINDOWS:
        res = [False, 'ICV']
    else:
        res = [False, 'ICV']
    if branch.startswith('2.4'):
        res = list(set([False, None]) & set(res))
    return res

def useSSEParameter(branch, platform, osType, compiler, useIPP, **params):
    if platform == PLATFORM_SKYLAKE_X:
        return [None]
    is64 = params.get('is64', True)
    if useIPP != False:
        return [None]
    if not branch.startswith('2.4') and platform != PLATFORM_DEFAULT:
        return [False]
    if osType == OSType.WINDOWS and compiler == PlatformWindowsCompiler[platform][-1] and is64:
        return [None, False]
    if platform == PLATFORM_DEFAULT and osType == OSType.LINUX and is64:
        return [None, False]
    return [None]

def useOpenCLParameter(platform, osType, compiler, **params):
    if platform == PLATFORM_SKYLAKE_X:
        return [True, False]
    is64 = params.get('is64', None)
    useSSE = params.get('useSSE', None)
    if osType == OSType.ANDROID:
        return [False]
    if useSSE == False:
        return [False]
    if osType == OSType.WINDOWS:
        if compiler == PlatformWindowsCompiler[platform][-1]:
            if platform == PLATFORM_DEFAULT:
                return [True, False]
            else:
                return [True]
    if osType == OSType.MACOSX:
        return [True, False]
    if osType == OSType.LINUX:
        return [False] if is64 is False else [True, False]
    return [False]

def testOpenCLParameter(platform, osType, compiler, useOpenCL, **params):
#    if osType == OSType.MACOSX:
#        return [False]
    return [useOpenCL]

def useDebugParameter(platform, osType, compiler, useIPP, **params):
    if platform == PLATFORM_SKYLAKE_X:
        return [None]
    useSSE = params.get('useSSE', None)
    if useSSE != False or platform != PLATFORM_DEFAULT:
        return [None]
    return [None, True]

def useShared(branch, platform, osType, useIPP, **params):
    if platform == PLATFORM_SKYLAKE_X:
        return [True]
    is64 = params.get('is64', None)
    compiler = params.get('compiler', None)
    isDebug = params.get('isDebug', None)
    enableStatic = False
    if platform == PLATFORM_DEFAULT and compiler == WinCompiler.VC15:
        return [True] # without static builds
    if platform == PLATFORM_DEFAULT and not is64 == False and not osType == OSType.ANDROID and not isDebug:
        enableStatic = True
    if not branch.startswith('2.4') and useIPP != 'ICV':
        enableStatic = False
    return [True, False] if enableStatic else [True]

def availableDockerImage(platform, osType, testOpenCL, **params):
    if osType == OSType.LINUX:
        if platform == PLATFORM_SKYLAKE_X and testOpenCL:
            return [(None, 'ubuntu:16.04')]
        return [None] #, INTEL_COMPILER_DOCKER_CURRENT]
    else:
        return [None]


from factory_builders_aggregator import *
from factory_helpers import *
import factory_ocl
import factory_docs
from factory_android import AndroidPackFactory
from factory_arm import ARMv7Factory, ARMv8Factory
from factory_ios import iOSFactory
from factory_linux import LinuxPrecommitFactory
from factory_valgrind import ValgrindFactory
from factory_coverage import CoverageFactory
from factory_winpack import WinPackBuild, WinPackBindings, WinPackDocs, WinPackTest, WinPackController, WinPackCreate, WinPackUpload

# Current "top-level" factory
OpenCVBuildFactory = factory_ocl.OCL_factory

builders = []
schedulers = []

def addConfiguration(descriptor):
    global builders, schedulers
    (new_builders, new_schedulers) = descriptor.Register()
    builders = builders + new_builders
    schedulers = schedulers + new_schedulers

# Nightly builders
for branch in ['2.4', '3.4', 'master']:
    addConfiguration(
        SetOfBuildersWithSchedulers(branch=branch, nameprefix='check-',
            genForce=True, genNightly=True, nightlyHour=21,
            builders=[
                SetOfBuilders(
                    factory_class=OpenCVBuildFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly']),
                    variate=[
                        dict(platform=platformParameter),
                        dict(osType=osTypeParameter),
                    ] + androidParameters() + [
                        dict(is64=is64ParameterCheck),
                        dict(compiler=availableCompilers),
                        dict(cmake_toolset=availableToolset),
                        dict(useIPP=useIPPParameter),
                        dict(useSSE=useSSEParameter),
                        dict(useOpenCL=useOpenCLParameter),
                        dict(testOpenCL=testOpenCLParameter),
                        dict(isDebug=useDebugParameter),
                        dict(buildShared=useShared),
                        dict(dockerImage=availableDockerImage),
                    ]
                ),
                SetOfBuilders(
                    factory_class=factory_docs.Docs_factory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'docs'], platform=PLATFORM_DEFAULT,
                                     osType=OSType.LINUX)
                ),
            ] + ([
                SetOfBuilders(
                    factory_class=iOSFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'ios_pack'], platform=PLATFORM_DEFAULT)
                ),
                SetOfBuilders(
                    factory_class=ARMv7Factory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'arm'], platform=PLATFORM_DEFAULT)
                ),
                SetOfBuilders(
                    factory_class=CoverageFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'coverage'], platform=PLATFORM_ANY,
                                     osType=OSType.LINUX, isDebug=True, useName='coverage')
                ),
                SetOfBuilders(
                    factory_class=AndroidPackFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'android_pack'], platform=PLATFORM_DEFAULT,
                                     osType=OSType.ANDROID, is64=True, useName='pack')
                ),
                SetOfBuilders(
                    factory_class=ARMv8Factory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'arm'], platform=PLATFORM_DEFAULT)),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'powerpc'], useName='powerpc-64le', dockerImage='powerpc64le')),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'js'], useName='javascript-emscripten', dockerImage='javascript')),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'cuda'], useName='cuda', dockerImage='ubuntu-cuda:16.04')),
            ] if branch != '2.4' else [])

        )
    )
    addConfiguration(
        SetOfBuildersWithSchedulers(
            branch=branch, nameprefix='weekly-',
            genForce=True, genNightly=True, nightlyHour=5, dayOfWeek=5,
            builders=([
                SetOfBuilders(
                    factory_class=iOSFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['weekly', 'ios_pack'], platform=PLATFORM_DEFAULT)
                ),
                SetOfBuilders(
                    factory_class=ARMv7Factory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['weekly', 'arm'], platform=PLATFORM_DEFAULT)
                ),
                SetOfBuilders(
                    factory_class=CoverageFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['weekly', 'coverage'], platform=PLATFORM_ANY,
                                     osType=OSType.LINUX, isDebug=True, useName='coverage')
                ),
                SetOfBuilders(
                    factory_class=AndroidPackFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['weekly', 'android_pack'], platform=PLATFORM_DEFAULT,
                                     osType=OSType.ANDROID, is64=True, useName='pack')
                ),
            ] if branch == '2.4' else []) + [
                SetOfBuilders(
                    factory_class=ValgrindFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['weekly', 'valgrind'], platform=PLATFORM_DEFAULT,
                                     osType=OSType.LINUX, isDebug=True, useName='valgrind')),
            ] + ([
                SetOfBuilders(
                    factory_class=ValgrindFactory,
                    init_params=dict(branch=branch, tags=['weekly', 'valgrind'], platform=PLATFORM_DEFAULT,
                                     osType=OSType.LINUX, isDebug=True, useName='valgrind', isContrib=True)),
                SetOfBuilders(
                    factory_class=CoverageFactory,
                    init_params=dict(isContrib=True, branch=branch, tags=['weekly', 'coverage', 'contrib'], platform=PLATFORM_DEFAULT,
                                     osType=OSType.LINUX, isDebug=True, useName='coverage')),
            ] if branch != '2.4' else [])
        )
    )

    if branch != '2.4':
        addConfiguration(
            SetOfBuildersWithSchedulers(branch=branch, nameprefix='checkcontrib-',
                genForce=True, genNightly=True, nightlyHour=22 if branch == 'master' else 23,
                builders=[
                    # OpenCV Contrib
                    SetOfBuilders(
                        factory_class=OpenCVBuildFactory,
                        init_params=dict(isContrib=True, branch=branch, tags=['nightly']),
                        variate=[
                            dict(platform=platformParameter),
                            dict(osType=osTypeParameter),
                        ] + androidParameters() + [
                            dict(is64=is64ParameterCheck),
                            dict(compiler=availableCompilers),
                            dict(useOpenCL=useOpenCLParameter),
                            dict(testOpenCL=testOpenCLParameter),
                        ]
                    ),
                    SetOfBuilders(
                        factory_class=factory_docs.Docs_factory,
                        init_params=dict(isContrib=True, branch=branch, tags=['nightly', 'docs'], platform=PLATFORM_DEFAULT,
                                         osType=OSType.LINUX)
                    ),
                    SetOfBuilders(
                        factory_class=AndroidPackFactory,
                        init_params=dict(isContrib=True, branch=branch, tags=['nightly', 'android_pack'], platform=PLATFORM_DEFAULT,
                                         osType=OSType.ANDROID, is64=True, useName='pack-contrib')
                    ),
                    SetOfBuilders(
                        factory_class=iOSFactory,
                        init_params=dict(isContrib=True, branch=branch, tags=['nightly', 'ios_pack'], platform=PLATFORM_DEFAULT)
                    ),
                    SetOfBuilders(
                        factory_class=ARMv7Factory,
                        init_params=dict(isContrib=True, branch=branch, tags=['nightly', 'arm'], platform=PLATFORM_DEFAULT)
                    ),
                    SetOfBuilders(
                        factory_class=ARMv8Factory,
                        init_params=dict(isContrib=True, branch=branch, tags=['nightly', 'arm'], platform=PLATFORM_DEFAULT)
                    ),
                ]
            )
        )


    addConfiguration(
        SetOfBuildersWithSchedulers(branch=branch, nameprefix='winpackbuild-',
            genTrigger=True, genForce=True,
            builders=[
                SetOfBuilders(
                    factory_class=WinPackBuild,
                    init_params=dict(branch=branch, tags=['pack-' + branch], osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT),
                    variate=[
                        dict(buildShared=[True, False] if branch == '2.4' else [True]),
                        dict(is64=[True, False] if branch == '2.4' else [True]),
                        dict(compiler=['vc14'] if branch == '2.4' else ['vc14', 'vc15']),
                    ]
                ),
                SetOfBuilders(
                    factory_class=WinPackBindings,
                    init_params=dict(branch=branch, tags=['pack-' + branch], osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT, buildShared=False),
                    variate=[
                        dict(is64=[True, False]),
                        dict(compiler=['vc14']),
                    ]
                )
            ] +
            ([
                SetOfBuilders(
                    factory_class=WinPackDocs,
                    init_params=dict(branch=branch, tags=['pack-' + branch], osType=OSType.LINUX, platform=PLATFORM_DEFAULT, is64=True),
                    variate=[],
                ),
            ] if branch == '2.4' else [])
        )
    )
    addConfiguration(
        SetOfBuildersWithSchedulers(nameprefix='winpack-', branch=branch,
            genForce=True, genNightly=True, nightlyHour=3 if branch == '2.4' else 0, dayOfWeek = 6 if branch == '2.4' else '*',
            builders=SetOfBuilders(
                factory_class=WinPackController,
                init_params=dict(
                    osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT,
                    buildTriggerName='winpackbuild-trigger_' + branch,
                    createTriggerName='winpackcreate-trigger_' + branch,
                    branch=branch, tags=['pack-' + branch])
            )
        )
    )
    addConfiguration(
        SetOfBuildersWithSchedulers(nameprefix='winpackcreate-', branch=branch,
            genForce=True, genTrigger=True,
            builders=SetOfBuilders(
                factory_class=WinPackCreate,
                init_params=dict(osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT,
                    testsTriggerName='winpacktests-trigger_' + branch,
                    completionTriggerName='winpackupload-trigger_' + branch,
                    branch=branch, tags=['pack-' + branch])
            )
        )
    )
    addConfiguration(
        SetOfBuildersWithSchedulers(branch=branch, nameprefix='winpacktests-',
            genTrigger=True,
            builders=SetOfBuilders(
                factory_class=WinPackTest,
                init_params=dict(branch=branch, tags=['pack-' + branch], osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT),
                variate=[
                    dict(buildShared=[True, False]),
                    dict(is64=[True, False] if branch == '2.4' else [True]),
                    dict(compiler=['vc14'] if branch == '2.4' else ['vc14', 'vc15']),
                ]
            )
        )
    )
    addConfiguration(
        SetOfBuildersWithSchedulers(nameprefix='winpackupload-', branch=branch,
            genForce=True, genTrigger=True,
            builders=SetOfBuilders(
                factory_class=WinPackUpload,
                init_params=dict(
                    osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT,
                    branch=branch, tags=['pack-' + branch],
                    #perfTestsTriggerName='perftests-trigger_' + branch,
                )
            )
        )
    )

    #addConfiguration(
    #    SetOfBuildersWithSchedulers(branch=branch, nameprefix='perftests-',
    #        genForce=True, genTrigger=True,
    #        builders=[]
    #    )
    #)

# end: for branch in ['2.4', '3.4', 'master']


precommitFactory = precommit(platform(PLATFORM_DEFAULT)(OpenCVBuildFactory))
precommitFactory = IPP_ICV(precommitFactory)
LinuxPrecommit = precommit(platform(PLATFORM_ANY)(LinuxPrecommitFactory))
WindowsPrecommit64 = windows(precommitFactory)
WindowsPrecommit32 = windows32(precommitFactory)
MacOSXPrecommit = macosx(OpenCL_noTest(precommitFactory))
AndroidPrecommit = android(precommitFactory)
OCLPrecommit = windows(OpenCL(precommitFactory))
OCLLinuxPrecommit = linux(OpenCL(platform(PLATFORM_DEFAULT)(precommitFactory)))
OCLMacPrecommit = macosx(OpenCL(precommitFactory))
LinuxPrecommitNoOpt = LinuxPrecommit
DocsPrecommit = linux(precommit(platform(PLATFORM_ANY)(factory_docs.Docs_factory)))
ARMv7Precommit = linux(precommit(platform(PLATFORM_DEFAULT)(ARMv7Factory)))
ARMv8Precommit = linux(precommit(platform(PLATFORM_DEFAULT)(ARMv8Factory)))
iOSPrecommit = precommit(platform(PLATFORM_DEFAULT)(iOSFactory))

addConfiguration(
    SetOfBuildersWithSchedulers(branch='branch', nameprefix='precommit-',
        genForce=True, genNightly=False,
        builders=[
            LinuxPrecommit(builderName='precommit_linux64'),
            linux32(LinuxPrecommit)(builderName='precommit_linux32', buildWithContrib=False),
            #LinuxPrecommit(builderName='precommit_linux64-icc', dockerImage='ubuntu-icc:16.04'),
            OCLLinuxPrecommit(builderName='precommit_opencl_linux', dockerImage='ubuntu:16.04', cmake_parameters={'OPENCV_CXX11':'ON', 'WITH_HALIDE':'ON', 'WITH_TBB':'ON'}),
            LinuxPrecommitNoOpt(builderName='precommit_linux64_no_opt', useIPP=False, useSSE=False, useOpenCL=False, isDebug=True, buildWithContrib=False),
            WindowsPrecommit64(builderName='precommit_windows64-vc15', compiler=WinCompiler.VC15, cmake_parameters={'OPENCV_EXTRA_CXX_FLAGS': '/std:c++latest', 'WITH_OPENEXR': 'OFF'}),
            WindowsPrecommit64(builderName='precommit_windows64'),
            #WindowsPrecommit64(builderName='precommit_windows64-icc', cmake_toolset=INTEL_COMPILER_TOOLSET_CURRENT),
            OCLPrecommit(builderName='precommit_opencl', cmake_parameters={'XWITH_TBB':'ON', 'XBUILD_TBB':'ON'}),
            OCLPrecommit(builderName='precommit_opencl-vc15', compiler=WinCompiler.VC15),
            WindowsPrecommit32(builderName='precommit_windows32'),
            MacOSXPrecommit(builderName='precommit_macosx'),
            OCLMacPrecommit(builderName='precommit_opencl_macosx'),
            iOSPrecommit(builderName='precommit_ios', tags=['ios_pack']),
            AndroidPrecommit(builderName='precommit_android'),
            ARMv7Precommit(builderName='precommit_armv7', tags=['arm']),
            ARMv8Precommit(builderName='precommit_armv8', tags=['arm']),
            DocsPrecommit(builderName='precommit_docs', tags=['docs']),
            precommit(platform(PLATFORM_DEFAULT)(AndroidPackFactory))(builderName='precommit_pack_android', buildWithContrib=False, tags=['android_pack']),
            LinuxPrecommit(builderName='precommit_custom_linux', dockerImage='is_not_set_but_required'),

            contrib(LinuxPrecommit)(builderName='precommit-contrib_linux64'),
            #contrib(LinuxPrecommit)(builderName='precommit-contrib_linux64-icc', dockerImage='ubuntu-icc:16.04'),
            contrib(OCLLinuxPrecommit)(builderName='precommit-contrib_opencl_linux', dockerImage='ubuntu:16.04'),
            contrib(LinuxPrecommitNoOpt)(builderName='precommit-contrib_linux64_no_opt', useIPP=False, useSSE=False, useOpenCL=False, isDebug=True),
            contrib(WindowsPrecommit64)(builderName='precommit-contrib_windows64'),
            #contrib(WindowsPrecommit64)(builderName='precommit-contrib_windows64-icc', cmake_toolset=INTEL_COMPILER_TOOLSET_CURRENT),
            contrib(OCLPrecommit)(builderName='precommit-contrib_opencl'),
            contrib(WindowsPrecommit32)(builderName='precommit-contrib_windows32'),
            contrib(MacOSXPrecommit)(builderName='precommit-contrib_macosx'),
            contrib(OCLMacPrecommit)(builderName='precommit-contrib_opencl_macosx'),
            contrib(iOSPrecommit)(builderName='precommit-contrib_ios', tags=['ios_pack']),
            contrib(AndroidPrecommit)(builderName='precommit-contrib_android'),
            contrib(ARMv7Precommit)(builderName='precommit-contrib_armv7', tags=['arm']),
            contrib(ARMv8Precommit)(builderName='precommit-contrib_armv8', tags=['arm']),
            contrib(DocsPrecommit)(builderName='precommit-contrib_docs', tags=['docs']),
            contrib(precommit(platform(PLATFORM_DEFAULT)(AndroidPackFactory)))(builderName='precommit-contrib_pack_android', tags=['android_pack']),
            contrib(LinuxPrecommit)(builderName='precommit-contrib_custom_linux64', dockerImage='is_not_set_but_required'),
        ]
    )
)

print "Configure builds... DONE"
