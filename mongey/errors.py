
class MongeyException(Exception):
    detail: str

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class ValidationError(MongeyException):
    pass


class DoNotSave(MongeyException):
    pass


class IntegrityError(MongeyException):
    pass


class MissingSubmodel(IntegrityError):
    pass


class WrongSubmodel(IntegrityError):
    pass


class UnknownSubmodel(IntegrityError):
    pass


class ObjectHasReferences(IntegrityError):
    pass


class ObjectSaveRequired(ValidationError):
    pass


class ModelDestroyed(IntegrityError):
    pass


class ConfigurationError(MongeyException):
    pass
