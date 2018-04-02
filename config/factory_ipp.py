from factory_common import CommonFactory

class IPP_factory(CommonFactory):

    def __init__(self, *args, **kwargs):
        self.useIPP = kwargs.pop('useIPP', None)  # Possible values: None, False, True, 'ICV'
        assert self.useIPP is None or self.useIPP == False or self.useIPP == True or self.useIPP == 'ICV'
        CommonFactory.__init__(self, *args, **kwargs)
        assert self.useIPP is None or self.useIPP != 'ICV' or not self.branch.startswith('2.4'), "2.4 doesn't support ICV"

    def initConstants(self):
        CommonFactory.initConstants(self)
        if self.useIPP == True:
            self.cmakepars['WITH_IPP'] = 'ON'
            self.env['BUILD_WITH_IPP'] = '1'
        elif self.useIPP == 'ICV':
            self.cmakepars['WITH_IPP'] = 'ON'
            self.env['BUILD_WITH_IPPICV'] = '1'
        else:
            self.cmakepars['WITH_IPP'] = 'OFF'

    def name(self):
        name = CommonFactory.name(self)
        ippsuffix = ''
        if self.useIPP is not None:
            if self.branch != '2.4':
                ippsuffix = 'noICV' if self.useIPP == False else (self.useIPP if self.useIPP != 'ICV' else '')
            elif self.branch is not None and self.branch.startswith('2.4'):
                ippsuffix = 'IPP' if self.useIPP else ''
        if len(ippsuffix) == 0:
            return name
        if name is not None and len(name) > 0:
            return name + '_' + ippsuffix
        return ippsuffix
