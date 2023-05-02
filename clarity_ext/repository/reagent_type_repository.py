from clarity_ext.utils import single
from clarity_ext.domain.reagent import ReagentType


class ReagentTypeRepository:
    def __init__(self, session):
        self.session = session

    def get_reagent_types(self, label):
        reagent_types = self.session.api.get_reagent_types(name=label)
        ret = list()
        for reagent_type_lims in reagent_types:
            reagent_type = ReagentType(label=label,
                                       category=reagent_type_lims.category,
                                       sequence=reagent_type_lims.sequence)
            ret.append(reagent_type)
        return ret

    def get_reagent_type(self, label):
        reagent_type = self.get_reagent_types(label=label)

        if len(reagent_type) == 1:
            return single(reagent_type)
        elif len(reagent_type) == 0:
            return None
        else:
            raise ValueError("'{}' is associated with more than one reagent type".format(label))




