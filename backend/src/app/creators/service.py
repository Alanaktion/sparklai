from app.creators.repository import CreatorRepository
from app.creators.schemas import CreatorCreate, CreatorUpdate
from app.db.models import Creator
from app.exceptions import NotFoundError, UnauthorizedError
from app.security.pin import hash_pin, verify_pin


class CreatorService:
    def __init__(self, repository: CreatorRepository):
        self._repository = repository

    async def list_all(self):
        return await self._repository.list_all()

    async def get_by_id_or_raise(self, id: int) -> Creator:
        creator = await self._repository.get_by_id(id)
        if not creator:
            raise NotFoundError("Creator", id)
        return creator

    async def signup(self, data: CreatorCreate) -> Creator:
        password_hash = hash_pin(data.pin)
        return await self._repository.create(
            name=data.name, pronouns=data.pronouns or "they/them", password_hash=password_hash
        )

    async def authenticate(self, creator_id: int, pin: str) -> Creator:
        creator = await self.get_by_id_or_raise(creator_id)
        if not verify_pin(pin, creator.password_hash):
            raise UnauthorizedError("Invalid PIN")
        return creator

    async def update_profile(self, creator: Creator, data: CreatorUpdate) -> Creator:
        fields = data.model_dump(exclude_unset=True)
        if not fields:
            return creator
        return await self._repository.update(creator, fields)
