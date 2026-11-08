import { MongoClient, type Db } from "mongodb";

const uri = process.env.MONGODB_URI ?? "mongodb://127.0.0.1:27017";
const dbName = process.env.MONGODB_DB ?? "dementia_face_memory";

declare global {
  // eslint-disable-next-line no-var
  var __dementiaMongoClient: Promise<MongoClient> | undefined;
}

const clientPromise = global.__dementiaMongoClient ?? new MongoClient(uri).connect();
if (process.env.NODE_ENV !== "production") global.__dementiaMongoClient = clientPromise;

export async function database(): Promise<Db> {
  return (await clientPromise).db(dbName);
}
