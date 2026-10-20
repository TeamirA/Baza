from .dtos import AddressDTO, RegistrationDTO
from .repositories import AddressRepository, UserRepository

MAX_ADDRESSES = 10


class AddressError(Exception):
    """A saved-address change that can't be made; the message is shown to the customer."""


class UserService:
    def __init__(self, users=None):
        self.users = users or UserRepository()

    def email_taken(self, email, exclude_user=None):
        return self.users.email_exists(email, exclude_user_id=getattr(exclude_user, "pk", None))

    def register(self, data: RegistrationDTO):
        return self.users.create(username=data.username, email=data.email, password=data.password)

    def change_email(self, user, email):
        email = email.strip().lower()
        self.users.set_email(user.pk, email)
        user.email = email
        return email


def _to_dto(address):
    return AddressDTO(
        id=address.pk,
        label=address.label,
        full_name=address.full_name,
        address=address.address,
        is_default=address.is_default,
    )


class AddressService:
    def __init__(self, addresses=None):
        self.addresses = addresses or AddressRepository()

    def list(self, user):
        return [_to_dto(a) for a in self.addresses.list_for_user(user.pk)]

    def add(self, user, full_name, address, label="", make_default=False):
        count = self.addresses.count_for_user(user.pk)
        if count >= MAX_ADDRESSES:
            raise AddressError(f"You can save up to {MAX_ADDRESSES} addresses. Delete one to add another.")
        # The first address is always the default.
        is_default = make_default or count == 0
        return _to_dto(self.addresses.create(user.pk, label.strip(), full_name.strip(), address.strip(), is_default))

    def save_from_checkout(self, user, full_name, address):
        """Saves a checkout address unless the account already has it. Returns True if saved."""
        if self.addresses.find_same(user.pk, full_name.strip(), address.strip()):
            return False
        try:
            self.add(user, full_name, address)
        except AddressError:
            return False
        return True

    def set_default(self, user, address_id):
        if not self.addresses.set_default(address_id, user.pk):
            raise AddressError("That address doesn't exist anymore.")

    def delete(self, user, address_id):
        if not self.addresses.delete(address_id, user.pk):
            raise AddressError("That address doesn't exist anymore.")
