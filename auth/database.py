from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

class Database:
    client: Optional[AsyncIOMotorClient] = None
    db = None

    @classmethod
    async def connect_db(cls):
        if cls.client is None:
            # MongoDB connection string with correct format
            MONGODB_URL = "mongodb+srv://puneetpunia7982:tl6zJanYNlGGxdei@cluster0.zebg4tv.mongodb.net/"
            cls.client = AsyncIOMotorClient(MONGODB_URL)
            cls.db = cls.client.tradingview
            print("Connected to MongoDB!")

    @classmethod
    async def close_db(cls):
        if cls.client is not None:
            cls.client.close()
            cls.client = None
            print("Disconnected from MongoDB!")

    @classmethod
    def get_db(cls):
        return cls.db 