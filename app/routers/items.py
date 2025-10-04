from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class Item(BaseModel):
    id: int
    name: str
    description: str | None = None


_items_db = [
    {"id": 1, "name": "Sample", "description": "A sample item"}
]


@router.get("/", response_model=list[Item])
def list_items():
    return _items_db


@router.get("/{item_id}", response_model=Item)
def get_item(item_id: int):
    for it in _items_db:
        if it["id"] == item_id:
            return it
    raise HTTPException(status_code=404, detail="Item not found")


@router.post("/", response_model=Item, status_code=201)
def create_item(item: Item):
    _items_db.append(item.dict())
    return item
