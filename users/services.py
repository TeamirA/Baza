from .dtos import RegistrationDTO
from .repositories import UserRepository


class UserService:
    def __init__(self, users=None):
        self.users = users or UserRepository()

    def email_taken(self, email):
        return self.users.email_exists(email)

    def register(self, data: RegistrationDTO):
        return self.users.create(username=data.username, email=data.email, password=data.password)
