import os
from build_utils import OSType
from build_utils import WinCompiler

print "Configure builds..."

import constants
from constants import trace, PLATFORM_DEFAULT, PLATFORM_INTEL

import buildbot_passwords
from buildbot.buildslave import BuildSlave

slaves = []
for slave in constants.slave:
    trace("Register slave: " + slave + " with passwd=*** and params=(%s)" % constants.slave[slave])
    slaves.append(BuildSlave(slave, buildbot_passwords.slave[slave], **(constants.slave[slave])))

platforms = [
    PLATFORM_DEFAULT,
    PLATFORM_INTEL,
    ]

PlatformWindowsCompiler = {
    PLATFORM_DEFAULT: [WinCompiler.VC12],
    PLATFORM_INTEL: [WinCompiler.VC14]
}

def osTypeParameter(platform, **params):
    if platform == PLATFORM_DEFAULT:
        return OSType.all
    elif platform == PLATFORM_INTEL:
        return [OSType.WINDOWS]
    assert False

def androidABIParameter(platform, osType, **params):
    if osType != OSType.ANDROID:
        return [None]
    if platform in ['xxxxx']:
        return [None, 'x86']
    else:
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
    if platform in ['xxxxx']:
        return [False]
    if osType == OSType.WINDOWS:
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
        res = [False]
    if branch.startswith('2.4'):
        res = list(set([False, None]) & set(res))
    return res

def useSSEParameter(branch, platform, osType, compiler, useIPP, **params):
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
    return [False]

def testOpenCLParameter(platform, osType, compiler, useOpenCL, **params):
    if osType == OSType.MACOSX:
        return [False]
    return [useOpenCL]

def useDebugParameter(platform, osType, compiler, useIPP, **params):
    useSSE = params.get('useSSE', None)
    if useSSE != False or platform != PLATFORM_DEFAULT:
        return [None]
    return [None, True]

def useShared(platform, **params):
    if platform == PLATFORM_INTEL:
        return [True, False]
    else:
        return [True]

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
for branch in ['2.4', 'master']:
    addConfiguration(
        SetOfBuildersWithSchedulers(branch=branch, nameprefix='check-',
            genForce=True, genNightly=True, nightlyHour=21,
            builders=[
                SetOfBuilders(
                    factory_class=OpenCVBuildFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly']),
                    variate=[
                        dict(platform=platforms),
                        dict(osType=osTypeParameter),
                    ] + androidParameters() + [
                        dict(is64=is64ParameterCheck),
                        dict(compiler=availableCompilers),
                        dict(useIPP=useIPPParameter),
                        dict(useSSE=useSSEParameter),
                        dict(useOpenCL=useOpenCLParameter),
                        dict(testOpenCL=testOpenCLParameter),
                        dict(isDebug=useDebugParameter),
                        dict(buildShared=useShared)
                    ]
                ),
                SetOfBuilders(
                    factory_class=factory_docs.Docs_factory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'docs'], platform=PLATFORM_DEFAULT,
                                     osType=OSType.MACOSX)
                ),
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
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'coverage'], platform=PLATFORM_DEFAULT,
                                     osType=OSType.LINUX, isDebug=True, useName='coverage')),
            ] + ([
                SetOfBuilders(
                    factory_class=AndroidPackFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'android_pack'], platform=PLATFORM_DEFAULT,
                                     osType=OSType.ANDROID, is64=True, useName='pack')
                )
            ] if branch != '2.4' else [])
        )
    )
    addConfiguration(
        SetOfBuildersWithSchedulers(
            branch=branch, nameprefix='weekly-',
            genForce=True, genNightly=True, nightlyHour=5, dayOfWeek=6,
            builders=[
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
                    factory_class=ARMv8Factory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'arm'], platform=PLATFORM_DEFAULT)),
            ] if branch != '2.4' else [])
        )
    )

    if branch != '2.4':
        addConfiguration(
            SetOfBuildersWithSchedulers(branch=branch, nameprefix='checkcontrib-',
                genForce=True, genNightly=True, nightlyHour=21,
                builders=[
                    # OpenCV Contrib
                    SetOfBuilders(
                        factory_class=OpenCVBuildFactory,
                        init_params=dict(isContrib=True, branch=branch, tags=['nightly']),
                        variate=[
                            dict(platform=platforms),
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
                                         osType=OSType.MACOSX)
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
                    SetOfBuilders(
                        factory_class=CoverageFactory,
                        init_params=dict(isContrib=True, branch=branch, tags=['nightly', 'coverage', 'contrib'], platform=PLATFORM_DEFAULT,
                                         osType=OSType.LINUX, isDebug=True, useName='coverage')),
                ]
            )
        )

precommitFactory = precommit(platform(PLATFORM_DEFAULT)(OpenCVBuildFactory))
precommitFactory = IPP_ICV(precommitFactory)
LinuxPrecommit = precommit(platform(PLATFORM_DEFAULT)(LinuxPrecommitFactory))
WindowsPrecommit64 = windows(precommitFactory)
WindowsPrecommit32 = windows32(precommitFactory)
MacOSXPrecommit = macosx(OpenCL_noTest(precommitFactory))
AndroidPrecommit = android(precommitFactory)
OCLPrecommit = windows(OpenCL(precommitFactory))
LinuxPrecommitNoOpt = LinuxPrecommit
DocsPrecommit = macosx(precommit(platform(PLATFORM_DEFAULT)(factory_docs.Docs_factory)))
ARMv7Precommit = linux(precommit(platform(PLATFORM_DEFAULT)(ARMv7Factory)))
ARMv8Precommit = linux(precommit(platform(PLATFORM_DEFAULT)(ARMv8Factory)))
iOSPrecommit = precommit(platform(PLATFORM_DEFAULT)(iOSFactory))

addConfiguration(
    SetOfBuildersWithSchedulers(branch='branch', nameprefix='precommit-',
        genForce=True, genNightly=False,
        builders=[
            LinuxPrecommit(builderName='precommit_linux64'),
            LinuxPrecommitNoOpt(builderName='precommit_linux64_no_opt', useIPP=False, useSSE=False, useOpenCL=False, isDebug=True, buildWithContrib=False),
            WindowsPrecommit64(builderName='precommit_windows64'),
            WindowsPrecommit32(builderName='precommit_windows32'),
            WindowsPrecommit64(builderName='precommit_windows_ten', platform=PLATFORM_INTEL, compiler=WinCompiler.VC14, buildShared=False, useAVX=True),
            OCLPrecommit(builderName='precommit_opencl'),
            OCLPrecommit(builderName='precommit_opencl-intel', platform=PLATFORM_INTEL, compiler=WinCompiler.VC14, buildShared=False, useAVX=True),
            MacOSXPrecommit(builderName='precommit_macosx'),
            iOSPrecommit(builderName='precommit_ios', tags=['ios_pack']),
            AndroidPrecommit(builderName='precommit_android'),
            ARMv7Precommit(builderName='precommit_armv7', tags=['arm']),
            ARMv8Precommit(builderName='precommit_armv8', tags=['arm']),
            DocsPrecommit(builderName='precommit_docs', tags=['docs']),
            precommit(platform(PLATFORM_DEFAULT)(AndroidPackFactory))(builderName='precommit_pack_android', tags=['android_pack']),

            contrib(LinuxPrecommit)(builderName='precommit-contrib_linux64'),
            contrib(LinuxPrecommitNoOpt)(builderName='precommit-contrib_linux64_no_opt', useIPP=False, useSSE=False, useOpenCL=False, isDebug=True),
            contrib(WindowsPrecommit64)(builderName='precommit-contrib_windows64'),
            contrib(WindowsPrecommit32)(builderName='precommit-contrib_windows32'),
            contrib(WindowsPrecommit64)(builderName='precommit-contrib_windows_ten', platform=PLATFORM_INTEL, compiler=WinCompiler.VC14, buildShared=False, useAVX=True),
            contrib(OCLPrecommit)(builderName='precommit-contrib_opencl'),
            contrib(OCLPrecommit)(builderName='precommit-contrib_opencl-intel', platform=PLATFORM_INTEL, compiler=WinCompiler.VC14, buildShared=False, useAVX=True),
            contrib(MacOSXPrecommit)(builderName='precommit-contrib_macosx'),
            contrib(iOSPrecommit)(builderName='precommit-contrib_ios', tags=['ios_pack']),
            contrib(AndroidPrecommit)(builderName='precommit-contrib_android'),
            contrib(ARMv7Precommit)(builderName='precommit-contrib_armv7', tags=['arm']),
            contrib(ARMv8Precommit)(builderName='precommit-contrib_armv8', tags=['arm']),
            contrib(DocsPrecommit)(builderName='precommit-contrib_docs', tags=['docs']),
            contrib(precommit(platform(PLATFORM_DEFAULT)(AndroidPackFactory)))(builderName='precommit-contrib_pack_android', tags=['android_pack']),
        ]
    )
)

print "Configure builds... DONE"
