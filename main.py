import logging
import re
import json
import requests
# اضافه کردن Flask
from flask import Flask, request, abort

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler, CallbackQueryHandler
)

# --- تنظیمات ---
# برای امنیت بیشتر، توکن رو از متغیرهای محیطی بخونید، نه مستقیماً در کد
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") 

MIXIN_API_URL = "https://mezonana.ir/api/management/v1/products/"
MIXIN_API_KEY = "aLbWTW5bS_y6k6yBs1__9gySUqtqLdFrZE7WkW2WcaTS2uOg7NoLc44xrURgsX_G" # این کلید رو هم بهتره از محیط بونید
MIXIN_MAIN_CATEGORY = "42"

# تعریف headers برای درخواست‌های GET
headers_get = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0'
}

# --- دیتابیس دستی ---
# این دیتابیس رو هم بهتره جای امن تری مثل دیتابیس واقعی (PostgreSQL, SQLite) یا Cloud Secret Manager ذخیره کنید
# فعلاً برای سادگی در همین فایل نگهش می‌داریم.
MANUAL_DATABASE = [
    {
        "chat_id": 867784641,
        "vendor_id": "1105867",
        "basalam_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIxMTM1IiwianRpIjoiMmJkOGJiOTM0MmM3YWE1YWNiYWM3ZDljZDhlMTc0MzRmMTBlZWMyMjQ4NzNmMjA5NDYyMWU0ZDI0NTA0NDc1YjlkZDg5MDg0MjA4M2I5ZDEiLCJpYXQiOjE3NDk5NjY2NDguNzcyMjMzLCJuYmYiOjE3NDk5NjY2NDguNzcyMjQxLCJleHAiOjE3ODE1MDI2NDguNjM5NDMyLCJzdWIiOiIxNDI2ODM2MyIsInNjb3BlcyI6WyJ2ZW5kb3IucHJvZHVjdC53cml0ZSIsImN1c3RvbWVyLnByb2ZpbGUucmVhZCJdLCJ1c2VyX2lkIjoxNDI2ODM2M30.OxxMTWOc0bly0hI4ESkhV_Sou0bZzusEELetqtaiXTkyjV22o45VPYJuygE_bnM-SUkJwRZunMiDhY2FyXM2QYPtg9YP86CpiC3Ixx3kKZMbhBgETKGpsklQ3FjmDMtukiweLLUccL28eyGfMOeu-cYQvuMBOzqEB-PT8CgwIi07kkl8jE5MIxoFrppto-vAfNlziHl9mgxT-CaPxT3l9Il0OoY47PLMah9uiM7MDkv-6eLNoxdIzy5oCpfFbcEwe2AO16DmLLD842oGhQVQ1YX595MgIUkbZvaXXyPRDzWTPWM-afOeDYpBOga0IWBA-47t-r4v1Fxmtl_b28_dtaIKU2fYiJgbqw7B7qSOfXfz-FjiQ4T4ge7sLLWxV96VDHSetZuWqJ34REm_kLjgeE6Dm6j2p-ThxHeQoaGfoOKnjU2rprtQwp5ucyghvjTw5Nrb4MB4EdDQRWkKu16rTaAjru6AuEIx7FA_zJr8ZXLdILbOCzi3BerIwiY49KO6_0q_BC8qyyIrGxYOqkO9szgb5gamRzuaSwYVvfWfBafOU3kJdRSxyhNcFkQusWVIkSoAyL_fHYvcTzsg-oyqQpG_CGnE2V2OWQ-04Q2fcZX5kK20cTzh8fAImV0PkJ0cyhIwCnb-Leo3K215UqB79U4avOdIxzbiPnaRClKQ9qM",
    },
    {
        "chat_id": 6632708699,
        "vendor_id": "1214396",
        "basalam_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiI1NTAiLCJqdGkiOiJlYmI1ODcyMWY0OWRjNDRmZDc4NDcwZWYzYTI2MGMxY2JiMGI3MWMyZjhlZGFmNTZiYTIxN2IxNTcwZGJlMTEyODQzYjNjY2I1ZDRlZDJkYiIsImlhdCI6MTc1MzA0NTMzMC4yNzYwNDIsIm5iZiI6MTc1MzA0NTMzMC4yNzYwNSwiZXhwIjoxNzg0NTgxMzMwLjIyMDQ4MSwic3ViIjoiMjAwMTYxMTYiLCJzY29wZXMiOlsib3JkZXItcHJvY2Vzc2luZyIsInZlbmRvci5wcm9maWxlLnJlYWQiLCJ2ZW5kb3IucHJvZmlsZS53cml0ZSIsImN1c3RvbWVyLnByb2ZpbGUud2VpdGUiLCJjdXN0b21lci5wcm9maWxlLnJlYWQiLCJjdXN0b21lci5vcmRlci5yZWFkIiwiY3VzdG9tZXIub3JkZXIud2l0ZSIsInZlbmRvci5wYXJjZWwucmVhZCIsInZlbmRvci5wYXJjZWwud3JpdGUiLCJjdXN0b21lci53YWxsZXQucmVhZCIsImN1c3RvbWVyLndhbGxldC53cml0ZSIsImN1c3RvbWVyLmNoYXQucmVhZCIsImN1c3RvbWVyLmNoYXQud3JpdGUiXSwidXNlcmRfaWQiOjIwMDE2MTE2fQ.jAImVP8WW-xF8ClfkHDHN9jLV4VpjGj3MMGoTP_6Rg3RRchJb8SFnEdoWaKJ0JAkXZjDSgrItN-ha1i8KS_5KIaLZekhxVN-cWEJb3TkZ75oRLd_e-sOc8kISOojGpwYwIhEfdqBX4yBEreWYjOXRVmzkUyAzkK7mfRjmEnayi6XXVPqWygyI3UzUhZizixnzD7AchIvBOufwPeTODTb2O3G_bCxzYL6TqKgVQcC2nub0E0oaDjp5yBPqXBqo4gk5RlAp7iyQyOzCyXE3WD2uxqTp3rhGUTaXSk7n-C_tDTq4BGYx2looqmVkwGZjwW5hsplLsHc0qcvGKToCa6CvMpFO9fZU0muiBpnJ8C2ls9yVgcJnFGNcNbTZPrkgmHswS8FmIjGW8sngGoVMpe8FErYBlcYB8O9Y2jOAtnO0Iq4Q2CJZVQUvN_4Mj3MmfxGyFaclzle6O3B4EYjm-DPspm7OXsblNk3bn_Mw0n8b9sdTE3Ep05fZSpj0EdMufwWCMNZv_N1B96yszepxR9EElXFANArsuElUdPp6Wc-8m6xX5dlHcMBWGBnffoKe2HnLki05mAiVpFUJLqh5rAayDoBZ2xCuCH_f67Rq2dlUw",
    },
    {
        "chat_id": 376782544,
        "vendor_id": "476077",
        "basalam_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIxMTE5IiwianRpIjoiNzk5ZTU0NjQ1NjczMTNlYjI1YzEzNmFmNGMzZGMwMjY2YTY2M2M1ZDI0NGExMGJjMDEwYjY5YzlkN2FhYTA3NjRjZjVkNzc2OGE1MjA0YjEiLCJpYXQiOjE3NTA5NTIyOTUuNDA4MjYyLCJuYmYiOjE3NTA5NTIyOTUuNDA4MjY2LCJleHAiOjE3ODI0ODgyOTUuMzYzMzcxLCJzdWIiOiIxNDM1NjI5Iiwic2NvcGVzIjpbInZlbmRvci5wcm9kdWN0LndyaXRlIiwiY3VzdG9tZXIucHJvZmlsZS5yZWFkIl0sInVzZXJfaWQiOjE0MzU2Mjl9.DunnIS5eswgh0LEeuv1b2RCsvdtaYy9oD0m78SwW8ajnaV4HVU8J-gGFKaybvqQyjOqqTTOEKhlXwYvr47OM9mZLe6vvTRJ1NmQC_qYnpkPtb2bvgVwEeuSpndK4UXhbMvmczNkMjkFbdOh8imo0nPQ4mUfxhCa6CvMpFO9fZU0muiBpnJ8C2ls9yVgcJnFGNcNbTZPrkgmHswS8FmIjGW8sngGoVMpe8FErYBlcYB8O9Y2jOAtnO0Iq4Q2CJZVQUvN_4Mj3MmfxGyFaclzle6O3B4EYjm-DPspm7OXsblNk3bn_Mw0n8b9sdTE3Ep05fZSpj0EdMufwWCMNZv_N1B96yszepxR9EElXFANArsuElUdPp6Wc-8m6xX5dlHcMBWGBnffoKe2HnLki05mAiVpFUJLqh5rAayDoBZ2xCuCH_f67Rq2dlUw",
    },
]

# --- تنظیم لاگینگ ---
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('telegram.ext._application').setLevel(logging.WARNING)
logging.getLogger('apscheduler').setLevel(logging.WARNING)

logger = logging.getLogger('product_cloner')
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

file_handler = logging.FileHandler('product_cloner.log')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# --- تابع ارسال به میکسین ---
def send_to_mixin(product_info: dict) -> (bool, str, int):
    """
    ارسال محصول به میکسین با تمام فیلدهای مورد نیاز
    """
    logger.info("شروع ارسال به میکسین")
    logger.info(product_info)
    if not product_info.get("name"):
        logger.error("نام محصول برای ارسال به میکسین خالی است")
        return False, "❌ نام محصول نمی‌تواند خالی باشد", None

    # تبدیل موجودی باسلام به فرمت میکسین
    stock = product_info.get("stock", 0)
    stock_type = "limited" if stock > 0 else "out_of_stock"

    data = {
        'name': product_info.get("name"),
        'main_category': int(MIXIN_MAIN_CATEGORY),
        'description': product_info.get("description", ""),
        'price': product_info.get("price", 0),
        'stock_type': stock_type,
        'stock': stock,
        'weight': product_info.get("weight", 0),
        'length': product_info.get("length", 0),
        'width': product_info.get("width", 0),
        'height': product_info.get("height", 0),
        'available': True,
        'is_digital': bool(product_info.get("virtual", False)),
        'has_variants': False
    }

    # اضافه کردن فیلدهای اختیاری اگر موجود باشند
    optional_fields = {
        'english_name': product_info.get("english_name"),
        'brand': product_info.get("brand_id"),
        'compare_at_price': product_info.get("compare_at_price"),
        'special_offer': product_info.get("special_offer", False),
        'special_offer_end': product_info.get("special_offer_end"),
        'barcode': product_info.get("barcode"),
        'max_order_quantity': product_info.get("max_order_quantity"),
        'guarantee': product_info.get("guarantee"),
        'seo_title': product_info.get("seo_title"),
        'seo_description': product_info.get("seo_description")
    }

    # حذف فیلدهای خالی
    for key, value in optional_fields.items():
        if value is not None:
            data[key] = value
    
    logger.info(f"ارسال به میکسین - داده‌ها: {json.dumps(data, ensure_ascii=False)}")
    
    headers = {
        'Authorization': f'Api-Key {MIXIN_API_KEY}', # این کلید رو هم بهتره از محیط بونید
        'Content-Type': 'application/json'
    }
    
    try:
        logger.info(f"درخواست POST به {MIXIN_API_URL}")
        resp = requests.post(
            MIXIN_API_URL,
            headers=headers,
            json=data,
            timeout=10
        )
        logger.info(f"پاسخ میکسین - کد: {resp.status_code}, متن: {resp.text}")

        if resp.status_code in (200, 201):
            product_id = resp.json().get('id')  # دریافت شناسه محصول
            return True, "✅ محصول با موفقیت به میکسین ارسال شد.", product_id
        else:
            logger.error(f"خطای میکسین: {resp.status_code} - {resp.text}")
            return False, f"❌ خطا در ارسال به میکسین: {resp.status_code} - {resp.text}", None

    except Exception as e:
        logger.error(f"خطای ارسال به میکسین: {str(e)}")
        return False, f"❌ خطا: {str(e)}", None

# --- فرایند کپی محصول ---
async def clone_product_process(chat_id, product_link, context: ContextTypes.DEFAULT_TYPE):
    logger.info("=== شروع فرآیند کپی محصول ===")
    logger.info(f"لینک محصول: {product_link}")

    # ۱. اطلاعات کاربر
    user_data = next((u for u in MANUAL_DATABASE if u["chat_id"] == chat_id), None)
    if not user_data:
        logger.error(f"کاربر {chat_id} در دیتابیس یافت نشد")
        await context.bot.send_message(chat_id, "❌ خطا: کاربر در سیستم ثبت نشده است.")
        return False

    # استخراج اطلاعات کاربر
    vendor_id = user_data["vendor_id"]
    basalam_token = user_data["basalam_token"]
    logger.info(f"اطلاعات کاربر: vendor_id={vendor_id}")

    # ۲. استخراج product_id
    product_id = product_link.strip().split('/')[-1]
    logger.info(f"شناسه محصول استخراج شده: {product_id}")

    # ۳. دریافت اطلاعات محصول
    get_url = f"https://core.basalam.com/v3/products/{product_id}"
    r = requests.get(get_url, headers=headers_get)
    
    if r.status_code == 200:
        product_info = r.json().get("data", {})
        logger.info("=== اطلاعات محصول باسلام ===")
        logger.info(f"نام: {product_info.get('title') or product_info.get('name', 'نامشخص')}")
        logger.info(f"قیمت: {product_info.get('price', 0):,} تومان")
        logger.info(f"موجودی: {product_info.get('inventory', 0)} عدد")
        logger.info(f"وزن: {product_info.get('weight', 0)} گرم")
        logger.info("=" * 50)
    else:
        logger.error(f"خطا در دریافت اطلاعات محصول: {r.status_code}")
        await context.bot.send_message(
            chat_id,
            f"❌ خطا در دریافت اطلاعات محصول از باسلام: {r.status_code}\n{r.text}"
        )
        return False # اضافه کردن return False در صورت خطا

    response_json = r.json()
    product_info = response_json.get("data", response_json)

    # لاگ و نمایش اطلاعات محصول
    logger.info(f"اطلاعات دریافتی از باسلام: {json.dumps(product_info, ensure_ascii=False, indent=2)}")
    
    product_details = (
        f"📦 اطلاعات محصول دریافتی از باسلام:\n\n"
        f"🏷 نام: {product_info.get('title') or product_info.get('name', 'نامشخص')}\n"
        f"💰 قیمت: {product_info.get('price', 0):,} ریال\n"
        f"📝 توضیحات: {product_info.get('description', 'بدون توضیحات')[:100]}...\n"
        f"📦 موجودی: {product_info.get('inventory', 0)} عدد\n"
        f"⚖️ وزن: {product_info.get('weight', 0)} گرم\n"
        f"🆔 شناسه: {product_info.get('id', 'نامشخص')}"
    )
    
    await context.bot.send_message(
        chat_id,
        product_details,
        parse_mode='HTML'
    )

    # ۴. استخراج فیلدهای ضروری
    photo_id = product_info.get("photo", {}).get("id")
    status_val = product_info.get("status", {}).get("value")
    # بررسی اینکه آیا category_id هم موجود است
    category_id = product_info.get("category", {}).get("id")

    if not all([photo_id, status_val, category_id]): # اضافه کردن category_id به بررسی
        details = f"photo={photo_id}, status={status_val}, category={category_id}"
        await context.bot.send_message(
            chat_id,
            f"❌ خطا: فیلدهای ضروری (تصویر، وضعیت یا دسته‌بندی) از API مبدا دریافت نشدند.\n{details}"
        )
        return False

    # ۵. ساخت payload برای باسلام
    payload = {
        "name":            product_info.get("name") or product_info.get("title"),
        "photo":           photo_id,
        "photos":          [p["id"] for p in product_info.get("photos", []) if p.get("id")],
        "status":          status_val,
        "brief":           product_info.get("brief", ""),
        "description":     product_info.get("description", ""),
        "category_id":     category_id, # استفاده از category_id استخراج شده
        "preparation_days": product_info.get("preparation_days", 2),
        "weight":          product_info.get("weight", 100),
        "package_weight":  product_info.get("weight", 100) + 50,
        "price":           product_info.get("price") or 0,
        "stock":           product_info.get("inventory") or 1,
        "is_wholesale":    bool(product_info.get("is_wholesale", False)),
        "virtual":         bool(product_info.get("virtual", False)),
        "shipping_city_ids":   [], # نیاز به تکمیل بر اساس کسب و کار شما
        "shipping_method_ids": [] # نیاز به تکمیل بر اساس کسب و کار شما
    }

    # ۶. ارسال به باسلام
    await context.bot.send_message(chat_id, "در حال ایجاد محصول در غرفه‌ی شما …")
    post_url = f"https://core.basalam.com/v3/vendors/{vendor_id}/products"
    headers_post = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {basalam_token}'
    }
    create_resp = requests.post(post_url, headers=headers_post, json=payload)

    # ۷. بررسی نتیجه
    if create_resp.status_code == 201:
        new_prod = create_resp.json().get("data", {})
        await context.bot.send_message(
            chat_id,
            f"✅ محصول با موفقیت در باسلام ساخته شد!\n"
            f"📦 نام: {new_prod.get('name')}\n"
            f"🆔 شناسه: {new_prod.get('id')}\n\n"
            "در حال ارسال به میکسین …"
        )

        # ساخت دیکشنری برای میکسین
        mixin_data = {
            "name": product_info["title"],
            "description": product_info.get("description", ""),
            "main_category": int(MIXIN_MAIN_CATEGORY),
            "price": product_info["price"],
            "stock": product_info["inventory"],
            "stock_type": "limited" if product_info["inventory"] > 0 else "out_of_stock",
            "weight": product_info.get("packaged_weight", 0),
            "length": 0,
            "width": 0,
            "height": 0,
            "available": product_info.get("is_available", True),
            "is_digital": False,
            "has_variants": product_info.get("has_selectable_variation", False),
            
            "preparation_days": product_info.get("preparation_days", 4),
            "seo_title": product_info["title"],
            "seo_description": product_info.get("summary") or product_info.get("description", "")[:250],
            "max_order_quantity": product_info.get("inventory", 1)
        }

        logger.info("=== اطلاعات آماده برای ارسال به میکسین ===")
        logger.info(f"نام: {mixin_data['name']}")
        logger.info(f"قیمت: {mixin_data['price']:,} تومان")
        logger.info(f"موجودی: {mixin_data['stock']} عدد")
        logger.info(f"وزن: {mixin_data['weight']} گرم")
        logger.info(f"زمان آماده‌سازی: {mixin_data['preparation_days']} روز")

        # ارسال به میکسین
        success, msg, mixin_product_id = send_to_mixin(mixin_data)
        if success and mixin_product_id:
            # آپلود تصاویر
            if await upload_images_to_mixin(mixin_product_id, product_info):
                msg += "\n✅ تصاویر محصول با موفقیت آپلود شدند."
            else:
                msg += "\n❌ خطا در آپلود تصاویر محصول."
        await context.bot.send_message(chat_id, msg)
        return True
    else:
        logger.error(f"خطا در ثبت محصول در باسلام: {create_resp.status_code} - {create_resp.text}")
        await context.bot.send_message(
            chat_id,
            f"❌ خطا در ثبت محصول در باسلام: {create_resp.status_code}\n{create_resp.text}"
        )
        return False

async def upload_images_to_mixin(product_id: int, product_info: dict) -> bool:
    """آپلود تصاویر محصول به میکسین"""
    logger.info(f"شروع آپلود تصاویر برای محصول {product_id}")
    
    headers = {
        'Authorization': f'Api-Key {MIXIN_API_KEY}' # این کلید رو هم بهتره از محیط بخونید
    }

    try:
        # تصویر اصلی
        main_image = product_info.get('photo', {})
        if main_image:
            image_url = main_image.get('original')
            if image_url:
                data = {
                    'image_url': image_url,
                    'image_alt': product_info.get('title', ''),
                    'default': True
                }
                
                response = requests.post(
                    f"{MIXIN_API_URL}{product_id}/images/",
                    headers=headers,
                    json=data
                )
                logger.info(f"آپلود تصویر اصلی: {response.status_code} - {response.text}") # اضافه کردن response.text

        # سایر تصاویر
        other_images = product_info.get('photos', [])
        for img in other_images:
            image_url = img.get('original')
            if image_url:
                data = {
                    'image_url': image_url,
                    'image_alt': product_info.get('title', ''),
                    'default': False
                }
                
                response = requests.post(
                    f"{MIXIN_API_URL}{product_id}/images/",
                    headers=headers,
                    json=data
                )
                logger.info(f"آپلود تصویر اضافی: {response.status_code} - {response.text}") # اضافه کردن response.text

        return True

    except Exception as e:
        logger.error(f"خطا در آپلود تصاویر: {str(e)}")
        return False

# --- منوها و هندلرها ---
MAIN_MENU, AWAITING_LINK = range(2)

def get_main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 کپی محصول", callback_data='clone_product')],
        [InlineKeyboardButton("❓ راهنما",  callback_data='help'),
         InlineKeyboardButton("📞 پشتیبانی", callback_data='support')]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"سلام {update.effective_user.first_name}!\n"
        "ربات کپی محصول باسلام و میکسین آماده است.",
        reply_markup=get_main_menu_keyboard()
    )
    return MAIN_MENU

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'clone_product':
        await query.edit_message_text(
            "لینک محصول باسلام را ارسال کنید:", reply_markup=None
        )
        return AWAITING_LINK
    elif query.data == 'help':
        await query.edit_message_text(
            "1. روی «کپی محصول» کلیک کنید.\n"
            "2. لینک محصول را بفرستید.\n"
            "3. صبر کنید تا محصول در باسلام و میکسین ثبت شود.",
            reply_markup=get_main_menu_keyboard()
        )
        return MAIN_MENU # باید به منوی اصلی برگردد
    elif query.data == 'support':
        await query.edit_message_text(
            "در صورت مشکل با پشتیبانی تماس بگیرید.", reply_markup=get_main_menu_keyboard()
        )
        return MAIN_MENU # باید به منوی اصلی برگردد
    return MAIN_MENU

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text
    if "basalam.com" not in link:
        await update.message.reply_text("لینک معتبر نیست، مجدداً تلاش کنید.", reply_markup=get_main_menu_keyboard()) # اضافه کردن کیبورد برای بازگشت
        return MAIN_MENU # در صورت لینک نامعتبر به منوی اصلی برگرد
    await update.message.reply_text("در حال پردازش …")
    success = await clone_product_process(update.effective_chat.id, link, context)
    # اگر clone_product_process موفق بود یا نبود، به منوی اصلی برمیگردیم
    await update.message.reply_text("بفرمایید کار دیگری؟", reply_markup=get_main_menu_keyboard())
    return MAIN_MENU

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لغو شد.", reply_markup=get_main_menu_keyboard())
    return ConversationHandler.END # پایان مکالمه و بازگشت به حالت اولیه

# --- تابع اصلی برای اجرای ربات ---
# این تابع برای Webhook تغییر می‌کند
def main_webhook():
    """
    تابع اصلی برای اجرای ربات با Webhook.
    این تابع مستقیماً اپلیکیشن Flask را برمی‌گرداند تا توسط gunicorn/WSGI اجرا شود.
    """
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # ایجاد و اضافه کردن ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [CallbackQueryHandler(main_menu_handler)],
            AWAITING_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    application.add_handler(conv_handler)

    # اتصال Dispatcher به Flask App
    # این قسمت مهمترین تغییر برای Webhook است
    
    # برای دسترسی به Dispatcher در بیرون از تابع main_webhook
    global dispatcher_instance
    dispatcher_instance = application.dispatcher

    return application


# ساخت یک نمونه از Flask App
app = Flask(__name__) # 'app' در اینجا همان شیء Flask است که توسط gunicorn/WSGI اجرا می‌شود.

@app.route('/')
def index():
    return "ربات تلگرام در حال اجراست!"

@app.route(f'/{TELEGRAM_BOT_TOKEN}', methods=['POST'])
async def telegram_webhook():
    """هندل کردن درخواست‌های وب‌هوک تلگرام"""
    update_data = request.get_json()
    if not update_data:
        abort(400)

    # ایجاد یک شیء Update از داده‌های دریافتی
    update = Update.de_json(update_data, main_webhook().bot) # یک نمونه bot از application ایجاد شده را پاس می‌دهیم

    # پردازش آپدیت توسط Dispatcher
    await main_webhook().process_update(update) # استفاده از process_update برای پردازش asynchronous
    
    return "ok"

# تابع اصلی برای اجرای لوکال (اختیاری)
if __name__ == '__main__':
    # این قسمت فقط برای تست لوکال است و باید Webhook را غیرفعال کنید.
    # برای اجرای لوکال با Long Polling (مثل کد اولیه شما):
    local_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU:       [CallbackQueryHandler(main_menu_handler)],
            AWAITING_LINK:   [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    local_app.add_handler(conv)
    print("ربات در حال اجرا (Long Polling) …")
    local_app.run_polling(poll_interval=1.0) # poll_interval را برای تست تنظیم کنید