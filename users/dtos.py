from dataclasses import dataclass


@dataclass(frozen=True)
class RegistrationDTO:
    username: str
    email: str
    password: str
