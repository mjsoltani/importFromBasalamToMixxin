import os
import logging
import re
import json
import requests
from flask import Flask, request, abort

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler, CallbackQueryHandler
)

# --- ۱. تنظیمات و متغیرهای محیطی ---
# توکن ربات تلگرام را از متغیرهای محیطی می‌خوانیم
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
# کلید API میکسین را از متغیرهای محیطی می‌خوانیم
MIXIN_API_KEY = os.environ.get("MIXIN_API_KEY")

# اگر توکن‌ها تنظیم نشده باشند، برنامه را متوقف می‌کنیم
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set.")
if not MIXIN_API_KEY:
    raise ValueError("MIXIN_API_KEY environment variable not set.")

MIXIN_API_URL = "https://mezonana.ir/api/management/v1/products/"
MIXIN_MAIN_CATEGORY = "42" # شناسه دسته بندی اصلی در میکسین

# تعریف headers برای درخواست‌های GET به باسلام
HEADERS_GET_BASALAM = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0'
}

# تعریف headers برای درخواست‌های POST به میکسین
HEADERS_POST_MIXIN = {
    'Authorization': f'Api-Key {MIXIN_API_KEY}',
    'Content-Type': 'application/json'
}

# --- ۲. دیتابیس دستی (قابل بهبود به دیتابیس واقعی) ---
# این دیتابیس فعلاً در کد است. برای مقیاس‌پذیری و امنیت بیشتر،
# پیشنهاد می‌شود از یک دیتابیس واقعی (مانند PostgreSQL) یا سرویس‌های ابری استفاده شود.
MANUAL_DATABASE = [
    {
        "chat_id": 867784641,
        "vendor_id": "1105867",
        "basalam_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIxMTM1IiwianRpIjoiMmJkOGJiOTM0MmM3YWE1YWNiYWM3ZDljZDhlMTc0MzRmMTBlZWMyMjQ4NzNmMjA5NDYyMWU0ZDI0NTA0NDc1YjlkZDg5MDg0NDI0MzI4OTk3NzA0MzgiLCJpYXQiOjE3NDk5NjY2NDguNzcyMjMzLCJuYmYiOjE3NDk5NjY2NDguNzcyMjQxLCJleHAiOjE3ODE1MDI2NDguNjM5NDMyLCJzdWIiOiIxNDI2ODM2MyIsInNjb3BlcyI6WyJ2ZW5kb3IucHJvZHVjdC53cml0ZSIsImN1c3RvbWVyLnByb2ZpbGUucmVhZCJdLCJ1c2VyX2lkIjoxNDI2ODM2M30.OxxMTWOc0bly0hI4ESkhV_Sou0bZzusEELetqtaiXTkyjV22o45VPYJuygE_bnM-SUkJwRZunMiDhY2FyXM2QYPtg9YP86CpiC3Ixx3kKZMbhBgETKGpsklQ3FjmDMtukiweLLUccL28eyGfMOeu-cYQvuMBOzqEB-PT8CgwIi07kkl8jE5MIxoFrppto-vAfNlziHl9mgxT-CaPxT3l9Il0OoY47PLMah9uiM7MDkv-6eLNoxdIzy5oCpfFbcEwe2AO16DmLLD842oGhQVQ1YX595MgIUkbZvaXXyPRDzWTPWM-afOeDYpBOga0IWBA-47t-r4v1Fxmtl_b28_dtaIKU2fYiJgbqw7B7qSOfXfz-FjiQ4T4ge7sLLWxV96VDHSetZuWqJ34REm_kLjgeE6Dm6j2p-ThxHeQoaGfoOKnjU2rprtQwp5ucyghvjTw5Nrb4MB4EdDQRWkKu16rTaAjru6AuEIx7FA_zJr8ZXLdILbOCzi3BerIwiY49KO6_0q_BC8qyyIrGxYOqkO9szgb5gamRzuaSwYVvfWfBafOU3kJdRSxyhNcFkQusWVIkSoAyL_fHYvcTzsg-oyqQpG_CGnE2V2OWQ-04Q2fcZX5kK20cTzh8fAImV0PkJ0cyhIwCnb-Leo3K215UqB79U4avOdIxzbiPnaRClKQ9qM",
    },
    {
        "chat_id": 6632708699,
        "vendor_id": "1214396",
        "basalam_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiI1NTAiLCJqdGkiOiJlYmI1ODcyMWY0OWRjNDRmZDc4NDcwZWYzYTI2MGMxY2JiMGI3MWMyZjhlZGFmNTZiYTIxN2IxNTcwZGJlMTEyODQzYjNjY2I1ZDRlZDJkYiIsImlhdCI6MTc1MzA0NTMzMC4yNzYwNDIsIm5iZiI6MTc1MzA0NTMzMC4yNzYwNSwiZXhwIjoxNzg0NTgxMzMwLjIyMDQ4MSwic3ViIjoiMjAwMTYxMTYiLCJzY29wZXMiOlsib3JkZXItcHJvY2Vzc2luZyIsInZlbmRvci5wcm9maWxlLnJlYWQiLCJ2ZW5kb3IucHJvZmlsZS53cml0ZSIsImN1c3R0b21lci5wcm9maWxlLnNlbnNpZ24iLCJjdXN0b21lci5wcm9maWxlLnJlYWQiLCJ2ZW5kb3IucHJvZHVjdC53cml0ZSIsInZlbmRvci5wcm9kdWN0LnJlYWQiLCJjdXN0b21lci5vcmRlci5yZWFkIiwiY3VzdG9tZXIub3JkZXIud3JpdGUiLCJ2ZW5kb3IucGFyY2VsLnJlYWQiLCJ2ZW5kb3IucGFyY2VsLndyaXRlIiwiY3VzdG9tZXIud2FsbGV0LnJlYWQiLCJjdXN0b21lci53YWxsZXQud3JpdGUiLCJjdXN0b21lci5jaGF0LnJlYWQiLCJjdXN0b21lci5jaGF0LndyaXRlIl0sInVzZXJfaWQiOjIwMDE2MTE2fQ.jAImVP8WW-xF8ClfkHDHN9jLV4VpjGj3MMGoTP_6Rg3RRchJb8SFnEdoWaKJ0JAkXZjDSgrItN-ha1i8KS_5KIaLZekhxVN-cWEJb3TkZ75oRLd_e-sOc8kISOojGpwYwIhEfdqBX4yBEreWYjOXRVmzkUyAzkK7mfRjmEnayi6XXVPqWygyI3UzUhZizixnzD7AchIvBOufwPeTODTb2O3G_bCxzYL6TqKgVQcC2nub0E0oaDjp5yBPqXBqo4gk5RlAp7iyQyOzCyXE3WD2uxqTp3rhGUTaXSk7n-C_tDTq4BGYx2looqmVkwGZjwW5hsplLsHc0qcvGKToCa6CvMpFO9fZU0muiBpnJ8C2ls9yVgcJnFGNcNbTZPrkgmHswS8FmIjGW8sngGoVMpe8FErYBlcYB8O9Y2jOAtnO0Iq4Q2CJZVQUvN_4Mj3MmfxGyFaclzle6O3B4EYjm-DPspm7OXsblNk3bn_Mw0n8b9sdTE3Ep05fZSpj0EdMufwWCMNZv_N1B96yszepxR9EElXFANArsuElUdPp6Wc-8m6xX5dlHcMBWGBnffoKe2HnLki05mAiVpFUJLqh5rAayDoBZ2xCuCH_f67Rq2dlUw",
    },
    {
        "chat_id": 376782544,
        "vendor_id": "476077",
        "basalam_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIxMTE5IiwianRpIjoiNzk5ZTU0NjQ1NjczMTNlYjI1YzEzNmFmNGMzZGMwMjY2YTY2M2M1ZDI0NGExMGJjMDEwYjY5YzlkN2FhYTA3NjRjZjVkNzc2OGE1MjA0YjEiLCJpYXQiOjE3NTA5NTIyOTUuNDA4MjYyLCJuYmYiOjE3NTA5NTIyOTUuNDA4MjY2LCJleHAiOjE3ODI0ODgyOTUuMzYzMzcxLCJzdWIiOiIxNDM1NjI5Iiwic2NvcGUycyI6WyJ2ZW5kb3IucHJvZHVjdC53cml0ZSIsImN1c3RvbWVyLnByb2ZpbGUucmVhZCJdLCJ1c2VyX2lkIjoxNDM1NjI5fQ.DunnIS5eswgh0LEeuv1b2RCsvdtaYy9oD0m78SwW8ajnaV4HVU8J-gGFKaybvqQyjOqqTTOEKhlXwYvr47OM9mZLe6vvTRJ1NmQC_qYnpkPtb2bvgVwEeuSpndK4UXhbMvmczNkMjkFbdOh8imo0nPQ4mUfxhCa6CvMpFO9fZU0muiBpnJ8C2ls9yVgcJnFGNcNbTZPrkgmHswS8FmIjGW8sngGoVMpe8FErYBlcYB8O9Y2jOAtnO0Iq4Q2CJZVQUvN_4Mj3MmfxGyFaclzle6O3B4EYjm-DPspm7OXsblNk3bn_Mw0n8b9sdTE3Ep05fZSpj0EdMufwWCMNZv_N1B96yszepxR9EElXFANArsuElUdPp6Wc-8m6xX5dlHcMBWGBnffoKe2HnLki05mAiVpFUJLqh5rAayDoBZ2xCuCH_f67Rq2dlUw",
    },
]

# --- ۳. تنظیمات لاگینگ ---
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

file_handler = logging.FileHandler('product_cloner.log') # در محیط سرور، این لاگ ممکن است به کنسول رندر هدایت شود
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# --- ۴. توابع اصلی ربات و منطق کپی محصول ---

def send_to_mixin(product_info: dict) -> (bool, str, int):
    """
    ارسال محصول به میکسین با تمام فیلدهای مورد نیاز
    """
    logger.info("شروع ارسال به میکسین")
    logger.info(product_info)
    if not product_info.get("name"):
        logger.error("نام محصول برای ارسال به میکسین خالی است")
        return False, "❌ نام محصول نمی‌تواند خالی باشد", None

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

    for key, value in optional_fields.items():
        if value is not None:
            data[key] = value
    
    logger.info(f"ارسال به میکسین - داده‌ها: {json.dumps(data, ensure_ascii=False)}")
    
    try:
        logger.info(f"درخواست POST به {MIXIN_API_URL}")
        resp = requests.post(
            MIXIN_API_URL,
            headers=HEADERS_POST_MIXIN, # استفاده از HEADERS_POST_MIXIN
            json=data,
            timeout=10
        )
        logger.info(f"پاسخ میکسین - کد: {resp.status_code}, متن: {resp.text}")

        if resp.status_code in (200, 201):
            product_id = resp.json().get('id')
            return True, "✅ محصول با موفقیت به میکسین ارسال شد.", product_id
        else:
            logger.error(f"خطای میکسین: {resp.status_code} - {resp.text}")
            return False, f"❌ خطا در ارسال به میکسین: {resp.status_code} - {resp.text}", None

    except requests.exceptions.RequestException as e: # هندل خطاهای شبکه
        logger.error(f"خطای شبکه در ارسال به میکسین: {str(e)}")
        return False, f"❌ خطای شبکه: {str(e)}", None
    except Exception as e:
        logger.error(f"خطای کلی در ارسال به میکسین: {str(e)}")
        return False, f"❌ خطا: {str(e)}", None

async def clone_product_process(chat_id, product_link, context: ContextTypes.DEFAULT_TYPE):
    logger.info("=== شروع فرآیند کپی محصول ===")
    logger.info(f"لینک محصول: {product_link}")

    user_data = next((u for u in MANUAL_DATABASE if u["chat_id"] == chat_id), None)
    if not user_data:
        logger.error(f"کاربر {chat_id} در دیتابیس یافت نشد")
        await context.bot.send_message(chat_id, "❌ خطا: کاربر در سیستم ثبت نشده است.")
        return False

    vendor_id = user_data["vendor_id"]
    basalam_token = user_data["basalam_token"]
    logger.info(f"اطلاعات کاربر: vendor_id={vendor_id}")

    product_id_basalam = product_link.strip().split('/')[-1]
    logger.info(f"شناسه محصول استخراج شده از باسلام: {product_id_basalam}")

    get_url = f"https://core.basalam.com/v3/products/{product_id_basalam}"
    try:
        r = requests.get(get_url, headers=HEADERS_GET_BASALAM, timeout=10) # استفاده از HEADERS_GET_BASALAM
        r.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        response_json = r.json()
        product_info = response_json.get("data", response_json)

    except requests.exceptions.RequestException as e:
        logger.error(f"خطا در دریافت اطلاعات محصول از باسلام: {e}")
        await context.bot.send_message(
            chat_id,
            f"❌ خطا در دریافت اطلاعات محصول از باسلام: \n{str(e)}"
        )
        return False

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

    photo_id = product_info.get("photo", {}).get("id")
    status_val = product_info.get("status", {}).get("value")
    category_id = product_info.get("category", {}).get("id")

    if not all([photo_id, status_val, category_id]):
        details = f"photo={photo_id}, status={status_val}, category={category_id}"
        logger.error(f"فیلدهای ضروری از API مبدا دریافت نشدند: {details}")
        await context.bot.send_message(
            chat_id,
            f"❌ خطا: فیلدهای ضروری (تصویر، وضعیت یا دسته‌بندی) از API مبدا دریافت نشدند.\n{details}"
        )
        return False

    # ساخت payload برای باسلام
    payload_basalam = {
        "name":            product_info.get("name") or product_info.get("title"),
        "photo":           photo_id,
        "photos":          [p["id"] for p in product_info.get("photos", []) if p.get("id")],
        "status":          status_val,
        "brief":           product_info.get("brief", ""),
        "description":     product_info.get("description", ""),
        "category_id":     category_id,
        "preparation_days": product_info.get("preparation_days", 2),
        "weight":          product_info.get("weight", 100),
        "package_weight":  product_info.get("weight", 100) + 50,
        "price":           product_info.get("price") or 0,
        "stock":           product_info.get("inventory") or 1,
        "is_wholesale":    bool(product_info.get("is_wholesale", False)),
        "virtual":         bool(product_info.get("virtual", False)),
        "shipping_city_ids":   [],
        "shipping_method_ids": []
    }

    await context.bot.send_message(chat_id, "در حال ایجاد محصول در غرفه‌ی شما در باسلام …")
    post_url_basalam = f"https://core.basalam.com/v3/vendors/{vendor_id}/products"
    headers_post_basalam = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {basalam_token}'
    }
    
    try:
        create_resp_basalam = requests.post(post_url_basalam, headers=headers_post_basalam, json=payload_basalam, timeout=10)
        create_resp_basalam.raise_for_status()

        new_prod_basalam = create_resp_basalam.json().get("data", {})
        await context.bot.send_message(
            chat_id,
            f"✅ محصول با موفقیت در باسلام ساخته شد!\n"
            f"📦 نام: {new_prod_basalam.get('name')}\n"
            f"🆔 شناسه: {new_prod_basalam.get('id')}\n\n"
            "در حال ارسال به میکسین …"
        )

        mixin_data = {
            "name": product_info.get("title") or product_info.get("name"),
            "description": product_info.get("description", ""),
            "main_category": int(MIXIN_MAIN_CATEGORY),
            "price": product_info.get("price", 0),
            "stock": product_info.get("inventory", 0),
            "stock_type": "limited" if product_info.get("inventory", 0) > 0 else "out_of_stock",
            "weight": product_info.get("packaged_weight", 0) or product_info.get("weight", 0),
            "length": 0,
            "width": 0,
            "height": 0,
            "available": product_info.get("is_available", True),
            "is_digital": bool(product_info.get("virtual", False)),
            "has_variants": product_info.get("has_selectable_variation", False),
            "preparation_days": product_info.get("preparation_days", 4),
            "seo_title": product_info.get("title") or product_info.get("name", ""),
            "seo_description": product_info.get("summary") or product_info.get("description", "")[:250],
            "max_order_quantity": product_info.get("inventory", 1)
        }

        logger.info("=== اطلاعات آماده برای ارسال به میکسین ===")
        logger.info(f"نام: {mixin_data['name']}")
        logger.info(f"قیمت: {mixin_data['price']:,} تومان")
        logger.info(f"موجودی: {mixin_data['stock']} عدد")
        logger.info(f"وزن: {mixin_data['weight']} گرم")
        logger.info(f"زمان آماده‌سازی: {mixin_data['preparation_days']} روز")

        success_mixin, msg_mixin, mixin_product_id = send_to_mixin(mixin_data)
        if success_mixin and mixin_product_id:
            if await upload_images_to_mixin(mixin_product_id, product_info):
                msg_mixin += "\n✅ تصاویر محصول با موفقیت آپلود شدند."
            else:
                msg_mixin += "\n❌ خطا در آپلود تصاویر محصول."
        await context.bot.send_message(chat_id, msg_mixin)
        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"خطای شبکه در ثبت محصول در باسلام: {e}")
        await context.bot.send_message(
            chat_id,
            f"❌ خطای شبکه در ثبت محصول در باسلام: \n{str(e)}"
        )
        return False
    except Exception as e:
        logger.error(f"خطای کلی در ثبت محصول در باسلام: {e}")
        await context.bot.send_message(
            chat_id,
            f"❌ خطای کلی در ثبت محصول در باسلام: \n{str(e)}"
        )
        return False

async def upload_images_to_mixin(product_id: int, product_info: dict) -> bool:
    """آپلود تصاویر محصول به میکسین"""
    logger.info(f"شروع آپلود تصاویر برای محصول {product_id}")
    
    try:
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
                    headers=HEADERS_POST_MIXIN, # استفاده از HEADERS_POST_MIXIN
                    json=data,
                    timeout=10
                )
                logger.info(f"آپلود تصویر اصلی: {response.status_code} - {response.text}")
                response.raise_for_status() # برای بررسی خطاهای HTTP

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
                    headers=HEADERS_POST_MIXIN, # استفاده از HEADERS_POST_MIXIN
                    json=data,
                    timeout=10
                )
                logger.info(f"آپلود تصویر اضافی: {response.status_code} - {response.text}")
                response.raise_for_status() # برای بررسی خطاهای HTTP

        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"خطای شبکه در آپلود تصاویر: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"خطای کلی در آپلود تصاویر: {str(e)}")
        return False

# --- ۵. منوها و هندلرها (ConversationHandler) ---
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
    await query.answer() # برای از بین بردن حالت لودینگ دکمه
    if query.data == 'clone_product':
        await query.edit_message_text(
            "لطفا لینک محصول باسلام را برای من ارسال کنید:", reply_markup=None # Remove keyboard
        )
        return AWAITING_LINK
    elif query.data == 'help':
        await query.edit_message_text(
            "📌 **راهنمای استفاده از ربات:**\n\n"
            "1. روی دکمه «🚀 کپی محصول» کلیک کنید.\n"
            "2. لینک کامل محصول مورد نظر خود را از وب‌سایت باسلام برای من بفرستید.\n"
            "3. صبر کنید تا ربات اطلاعات محصول را دریافت، پردازش و سپس در غرفه‌ی شما در باسلام و همچنین در میکسین ثبت کند.\n"
            "پس از اتمام عملیات، گزارش آن را دریافت خواهید کرد.",
            parse_mode='Markdown',
            reply_markup=get_main_menu_keyboard()
        )
        return MAIN_MENU 
    elif query.data == 'support':
        await query.edit_message_text(
            "📞 **پشتیبانی:**\n"
            "در صورت بروز هرگونه مشکل یا سوال، می‌توانید با پشتیبانی ما تماس بگیرید.\n"
            "آیدی تلگرام: @mjsoltani_ai\n"
            "همچنین می‌توانید از طریق ایمیل با ما در ارتباط باشید: m.javad.soltani@example.com", # ایمیل رو به ایمیل خودت تغییر بده
            parse_mode='Markdown',
            reply_markup=get_main_menu_keyboard()
        )
        return MAIN_MENU 
    return MAIN_MENU

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text
    # استفاده از regex برای اعتبارسنجی دقیق‌تر لینک باسلام
    if not re.match(r"https?://(?:www\.)?basalam\.com/.*", link):
        await update.message.reply_text(
            "❌ لینک معتبر نیست. لطفاً یک لینک صحیح از وب‌سایت باسلام ارسال کنید.",
            reply_markup=get_main_menu_keyboard()
        )
        return MAIN_MENU
    
    await update.message.reply_text("⏳ در حال پردازش لینک شما ... لطفا صبر کنید.")
    success = await clone_product_process(update.effective_chat.id, link, context)
    
    if success:
        await update.message.reply_text("✅ عملیات کپی محصول با موفقیت به پایان رسید.")
    else:
        await update.message.reply_text("❌ عملیات کپی محصول با خطا مواجه شد. لطفاً لاگ‌ها را بررسی کنید.")
        
    await update.message.reply_text("بفرمایید کار دیگری؟", reply_markup=get_main_menu_keyboard())
    return MAIN_MENU

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد.", reply_markup=get_main_menu_keyboard())
    return ConversationHandler.END

# --- ۶. ساخت اپلیکیشن Flask و PTB Application برای Webhook ---
# این Flask app است که توسط gunicorn/WSGI اجرا می‌شود.
# این باید در Global Scope تعریف شود تا gunicorn آن را پیدا کند.
app = Flask(__name__)

# این Application از python-telegram-bot است که تمام هندلرها را مدیریت می‌کند.
# یک بار در شروع برنامه تعریف می‌شود.
ptb_app: Application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# اضافه کردن ConversationHandler به ptb_app
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        MAIN_MENU: [CallbackQueryHandler(main_menu_handler)],
        AWAITING_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link)],
    },
    fallbacks=[CommandHandler('cancel', cancel), MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler_on_text)] # برای برگشت به منوی اصلی با پیام متنی
)
ptb_app.add_handler(conv_handler)

# اضافه کردن هندلر برای پیام‌های نامفهوم که کاربر را به منو هدایت کند
async def main_menu_handler_on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "پیام شما نامفهوم بود. لطفا از منو استفاده کنید:",
        reply_markup=get_main_menu_keyboard()
    )
    return MAIN_MENU

# --- ۷. روترهای Flask برای Webhook ---

@app.route('/')
async def index():
    """روت اصلی برای تست سلامت سرویس"""
    return "ربات تلگرام در حال اجراست!"

@app.route(f'/{TELEGRAM_BOT_TOKEN}', methods=['POST'])
async def telegram_webhook():
    """هندل کردن درخواست‌های وب‌هوک از تلگرام"""
    if not request.json:
        abort(400) # درخواست بدون JSON نامعتبر است

    update = Update.de_json(request.json, ptb_app.bot)
    
    # پردازش آپدیت به صورت asynchronous
    await ptb_app.process_update(update)
    
    return "ok"

# --- ۸. اجرای لوکال (فقط برای توسعه) ---
if __name__ == '__main__':
    # این قسمت فقط برای اجرای لوکال با Long Polling است.
    # برای دیپلوی روی Render/PythonAnywhere از این بخش استفاده نمی‌شود.
    
    # اطمینان از تنظیم توکن ها برای اجرای لوکال
    # اگر اینها را به صورت Environment Variables در سیستم لوکال خود ست نکرده‌اید،
    # می‌توانید موقتاً اینجا برای تست لوکال مقداردهی کنید:
    # os.environ["TELEGRAM_BOT_TOKEN"] = "7598112549:AAE1vjvqnp0FOF5yyIBpbYGDpnYW3Vfk9o8"
    # os.environ["MIXIN_API_KEY"] = "aLbWTW5bS_y6k6yBs1__9gySUqtqLdFrZE7WkW2WcaTS2uOg7NoLc44xrURgsX_G"

    # مطمئن شو که ptb_app برای اجرای لوکال دوباره ست‌آپ شود،
    # یا ptb_app را در یک تابع قرار دهیم که هم برای لوکال و هم برای وب‌هوک استفاده شود.
    # برای سادگی، یک Application جدید برای Long Polling می‌سازیم.
    
    print("ربات در حال اجرا (Long Polling) برای تست لوکال…")
    
    local_app_ptb = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler_local = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [CallbackQueryHandler(main_menu_handler)],
            AWAITING_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link)],
        },
        fallbacks=[CommandHandler('cancel', cancel), MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler_on_text)]
    )
    local_app_ptb.add_handler(conv_handler_local)
    
    local_app_ptb.run_polling(poll_interval=1.0, allowed_updates=Update.ALL_TYPES)