import os

import constants
from constants import trace

# ParametersGenerator(
#     init_params=dict(isPrecommit=False),
#     variate=[
#         dict(branch=['master', '2.4']),
#         dict(isWin=[True, False]),
#         dict(is64=lambda params: [True, False] if params['isWin'] else [True]),
#     ])
# will provide:
# {'is64': True, 'isPrecommit': False, 'branch': 'master', 'isWin': True}
# {'is64': False, 'isPrecommit': False, 'branch': 'master', 'isWin': True}
# {'is64': True, 'isPrecommit': False, 'branch': 'master', 'isWin': False}
# {'is64': True, 'isPrecommit': False, 'branch': '2.4', 'isWin': True}
# {'is64': False, 'isPrecommit': False, 'branch': '2.4', 'isWin': True}
# {'is64': True, 'isPrecommit': False, 'branch': '2.4', 'isWin': False}
#
def ParametersGenerator(init_params, variate):
    from pprint import pprint
    pprint(init_params)
    pprint(variate)
    size = len(variate)
    state = size * [-1]
    pos = 0
    while True:
        if pos == -1:
            break
        if pos == 0:
            params = init_params.copy()
        vset = variate[pos]
        assert len(vset.keys()) == 1
        pname = vset.keys()[0]
        pval = vset[pname]
        if hasattr(pval, '__call__'):
            pval = pval(**params)
        elif (hasattr(pval, '__name__') and pval.__name__ == '<lambda>'):
            pval = pval(params)
        state[pos] += 1
        if (state[pos] >= len(pval)):
            state[pos] = -1
            pos -= 1
            continue
        params[pname] = pval[state[pos]]
        if pos == size - 1:
            yield params.copy()
        else:
            pos += 1


class SetOfBuilders(object):

    def __init__(self, **kwargs):
        self.factory_class = kwargs.pop('factory_class', None)
        self.params_generator = kwargs.pop('params_generator', None)
        self.init_params = kwargs.pop('init_params', None)
        self.variate = kwargs.pop('variate', [])
        assert not (self.factory_class is None)
        assert not (self.init_params is None and self.params_generator is None)
        assert len(kwargs.keys()) == 0, 'Unknown parameters: ' + ' '.join(kwargs.keys())


    def GetListOfBuilders(self):
        builder_descriptors = []
        if self.params_generator:
            assert self.init_params is None
            for params in self.params_generator:
                builder_descriptors.append(self.factory_class(**params))
        if self.variate:
            for params in ParametersGenerator(self.init_params, self.variate):
                builder_descriptors.append(self.factory_class(**params))
        else:
            builder_descriptors.append(self.factory_class(**self.init_params))
        return builder_descriptors


    def RegisterBuilders(self):
        builders = []
        builderNames = []

        builder_descriptors = self.GetListOfBuilders()
        for builder in builder_descriptors:
            trace("Register builder: name=%s, slavenames=%s" % (builder.getName(), builder.getSlaves()))
            try:
                builders.append(builder.register())
                builderNames.append(builder.getName())
            except:
                trace("Can't register builder: %s" % repr(builder))
                raise

        self.builders = builders
        self.builderNames = builderNames

        return (builders, builderNames)



class SetOfBuildersWithSchedulers():

    def __init__(self, **kwargs):
        self.nameprefix = kwargs.pop('nameprefix', "")
        self.branch = kwargs.pop('branch', None)
        self.genForce = kwargs.pop('genForce', False)
        self.genTrigger = kwargs.pop('genTrigger', False)
        self.genNightly = kwargs.pop('genNightly', False)
        self.nightlyHour = kwargs.pop('nightlyHour', None)
        self.nightlyMinute = kwargs.pop('nightlyMinute', None)
        self.dayOfWeek = kwargs.pop('dayOfWeek', "*")
        self.builders = kwargs.pop('builders', None)
        assert self.builders
        assert not((not self.genNightly is True) and (not self.nightlyHour is None or not self.nightlyMinute is None))
        assert self.branch or self.genTrigger


    def Register(self):
        builders = []
        builderNames = []

        if isinstance(self.builders, list):
            for buildersSet in self.builders:
                if isinstance(buildersSet, SetOfBuilders):
                    (new_builders, new_builderNames) = buildersSet.RegisterBuilders()
                else:
                    builder = buildersSet
                    trace("Register builder: name=%s, slavenames=%s" % (builder.getName(), builder.getSlaves()))
                    new_builders = [builder.register()]
                    new_builderNames = [builder.getName()]

                builders = builders + new_builders
                builderNames = builderNames + new_builderNames
        else:
            (builders, builderNames) = self.builders.RegisterBuilders()

        schedulers = []

        from buildbot.schedulers.forcesched import ForceScheduler
        from buildbot.schedulers.timed import Nightly
        from buildbot.schedulers.triggerable import Triggerable

        branch = self.branch
        types = []
        if self.genForce: types.append('force')
        if self.genNightly: types.append('nightly')
        if self.genTrigger: types.append('trigger')
        if types:
            trace("Register schedulers (%s): branch=%s, builders = %s" %
                    (' + '.join(types), branch, builderNames))
        if branch is not None:
            codebase = constants.codebase[branch]
        if self.genForce:
            schedulers.append(ForceScheduler(name=self.nameprefix + 'force_' + branch,
                                             builderNames=builderNames,
                                             codebases=codebase.getCodebase()))
        if self.genNightly and not os.environ.get('DEBUG', False) and not os.environ.get('BUILDBOT_MANUAL', False):
            pref = 'nightly_' if self.dayOfWeek == '*' else 'daily_%s_' % self.dayOfWeek
            schedulers.append(Nightly(hour='*' if self.nightlyHour is None else self.nightlyHour,
                                      minute=0 if self.nightlyMinute is None else self.nightlyMinute,
                                      dayOfWeek = self.dayOfWeek,
                                      name=self.nameprefix + pref + branch, builderNames=builderNames,
                                      codebases=codebase.getCodebase(), branch=None))
        if self.genTrigger:
            schedulers.append(Triggerable(name=self.nameprefix + 'trigger' + ('_' + branch if branch is not None else ''),
                builderNames=builderNames, codebases=codebase.getCodebase()))

        self.builders = builders
        self.builderNames = builderNames
        self.schedulers = schedulers

        return (builders, schedulers)
