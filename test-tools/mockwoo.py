"""Test-only mock of the WooCommerce REST API (NOT a repo deliverable)."""
from fastapi import FastAPI, Request, HTTPException
app = FastAPI(); P=[]
O=[{"id":101,"status":"processing","total":"999.00","currency":"INR","date_created":"2026-10-09T10:00:00","payment_method_title":"Cash on delivery","billing":{"first_name":"Asha","last_name":"K"},"line_items":[{"name":"Test Shirt","quantity":1}]}]
def auth(r):
    if r.query_params.get("consumer_key")!="ck_test" or r.query_params.get("consumer_secret")!="cs_test": raise HTTPException(401,"bad key")
@app.get("/wp-json/wc/v3/products")
def lp(r:Request): auth(r); return P
@app.post("/wp-json/wc/v3/products")
async def cp(r:Request):
    auth(r); b=await r.json(); p={"id":len(P)+1,"name":b["name"],"price":b["regular_price"],"status":b["status"],"stock_status":"instock","permalink":"http://store/p/%d"%(len(P)+1)}; P.append(p); return p
@app.get("/wp-json/wc/v3/orders")
def lo(r:Request): auth(r); return O
@app.get("/wp-json/wc/v3/orders/{i}")
def go(i:int,r:Request):
    auth(r); return next(o for o in O if o["id"]==i)
@app.put("/wp-json/wc/v3/orders/{i}")
async def uo(i:int,r:Request):
    auth(r); b=await r.json(); o=next(o for o in O if o["id"]==i); o["status"]=b["status"]; return o
