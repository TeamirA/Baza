from dataclasses import dataclass


@dataclass(frozen=True)
class RegistrationDTO:
    username: str
    email: str
    password: str


@dataclass(frozen=True)
class AddressDTO:
    id: int
    label: str
    full_name: str
    address: str
    is_default: bool

    @property
    def title(self):
        return self.label or self.full_name

    @property
    def one_line(self):
        return ", ".join(part.strip() for part in self.address.splitlines() if part.strip())
