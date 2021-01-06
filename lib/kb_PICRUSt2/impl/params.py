import json

from .config import Var
from ..util.debug import dprint



def flatten(d):
    '''
    At most 1 level nesting
    Removes any nested dict's key
    '''
    d1 = d.copy()
    for k, v in d.items():
        if isinstance(v, dict):
            for k1, v1 in d1.pop(k).items():
                d1[k1] = v1
    return d1


class Params:


    DEFAULTS = {
        'create_amplicon_fps': True,
        'create_sample_fps': True,
    }

    def __init__(self, params):

        ## Flatten right away ##
        params = flatten(params)

        ## Validation
        self._validate(params)

        
        ## Custom transformations to internal state ##
        ## This is kind of silly ##
        ## But the code is written before I figure out how the narrative passes things ##

        if type(params.get('create_amplicon_fps')) is int:
            params['create_amplicon_fps'] = True if params['create_amplicon_fps'] == 1 else False
        if type(params.get('create_sample_fps')) is int:
            params['create_sample_fps'] = True if params['create_sample_fps'] == 1 else False
       
        ##
        self.params = params


    def _validate(self, params):
        '''
        None of params go directly to shell
        '''
        # TODO

        VALID = [
            'amplicon_matrix_upa',
            'create_amplicon_fps', 'create_sample_fps',
            #---
            'output_name',
            'workspace_id',
            'workspace_name',
        ]

        for p in params:
            if p not in VALID:
                raise Exception(p)




    def __getitem__(self, key):
        '''
        For required params (e.g., input UPAs, workspace stuff)
        Should not use this for default-backed params
        as those can be left off params
        so use `getd` for those
        '''
        return self.params[key]

    def getd(self, key):
        '''
        For default-backed params (e.g., tunable numbers)
        Like `get`
        Return the user-supplied value, or the default value if none was supplied
        '''
        if key not in self.DEFAULTS:
            raise Exception('`params.getd(x)` only applicable to params with defaults')

        return self.params.get(key, self.DEFAULTS[key])


    def __repr__(self) -> str:
        return 'Wrapper for params:\n%s' % (json.dumps(self.params, indent=4))


