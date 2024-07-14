import easyocr
import io
from PIL import Image
import ssl
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
import os
from typing import Dict, Optional
import logging
import time
from dotenv import load_dotenv

# Load environment variables from .env file in such format:
#
# AMBASSY_REQUEST_NUMBER=xxxxx
# AMBASSY_PROTECTION_CODE=xxxxxxx
# RETRY_COUNT=10
# AMBASSY_CITY=cityname

load_dotenv()

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
AMBASSY_REQUEST_NUMBER = os.environ["AMBASSY_REQUEST_NUMBER"]
AMBASSY_PROTECTION_CODE = os.environ["AMBASSY_PROTECTION_CODE"]
RETRY_COUNT = int(os.environ.get("RETRY_COUNT", "10"))
AMBASSY_CITY = os.environ["AMBASSY_CITY"]

# Set up logging to a local file
logging.basicConfig(filename='app.log', filemode='a', format='%(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger()

cookies = urllib.request.HTTPCookieProcessor()
ssl_ctx = ssl.create_default_context()
ssl_ctx.set_ciphers('AES128-SHA')
opener = urllib.request.build_opener(
    urllib.request.HTTPSHandler(context=ssl_ctx),
    urllib.request.HTTPRedirectHandler(),
    cookies,
)
opener.addheaders = [('User-agent', USER_AGENT)]

def http_req(url: str, form_data: Optional[Dict[str, str]] = None) -> bytes:
    """Make a request, accept any SSL certificate, and return the response. Stores cookies in a file."""
    logger.debug("Requesting %s with data %s", url, form_data)
    headers = {'User-Agent': USER_AGENT}
    data = urllib.parse.urlencode(form_data).encode() if form_data else None
    req = urllib.request.Request(url, data=data, headers=headers)
    response = opener.open(req)
    return response.read()

def get_soup(url: str, form_data: Optional[Dict[str, str]] = None) -> BeautifulSoup:
    response = http_req(url, form_data)
    return BeautifulSoup(response, "html.parser")

def extract_image_data_by_id(soup: BeautifulSoup, url: str) -> bytes:
    image_id = "ctl00_MainContent_imgSecNum"
    img = soup.find(id=image_id)
    if not img:
        raise ValueError(f"No image found with ID '{image_id}'")
    src: str = img.get("src")
    if not src:
        raise ValueError(f"No 'src' attribute found for image with ID '{image_id}'")
    src = "/".join(url.split("/")[:-1] + [src])
    image_bytes = http_req(src)
    return image_bytes

def extract_soup_form_data(soup: BeautifulSoup) -> Dict[str, str]:
    form = soup.find("form")
    if not form:
        raise ValueError("No form found in the given page")
    form_data: Dict[str, str] = {}
    for input in form.find_all("input"):
        name: str = input.get("name")
        value: str = input.get("value")
        if name:
            form_data[name] = value
    return form_data

class CaptchaSolvingError(ValueError):
    pass

def extract_capcha_image(source_image: bytes) -> bytes:
    pil_img = Image.open(io.BytesIO(source_image))
    pil_img = pil_img.crop((200, 0, 400, 200))
    img_byte_array = io.BytesIO()
    pil_img.save(img_byte_array, format="JPEG")
    image = img_byte_array.getvalue()
    return image

easyocr_reader = easyocr.Reader(["en"])

def solve_captcha(image: bytes) -> str:
    image = extract_capcha_image(image)
    result = easyocr_reader.readtext(
        image, allowlist="0123456789", min_size=10, detail=0, rotation_info=[90, 270],
        decoder='beamsearch', beamWidth=15,
        contrast_ths=0.2,
        text_threshold=0.01)
    logger.debug("Detected text: %s", result)
    if len(result) == 0:
        raise CaptchaSolvingError("No text found in the image")
    for r in result:
        if is_captcha_format_ok(r):
            return r
    txt = "".join(t for r in result for t in r if t.isdigit())
    if is_captcha_format_ok(txt):
        return txt
    if len(txt) > 6:
        return txt[:6]
    raise CaptchaSolvingError("No 6-digit number found in the image")

def is_captcha_format_ok(captcha: str) -> bool:
    return captcha.isdigit() and len(captcha) == 6

def fill_form_data(data: Dict[str, str], captcha_image: bytes) -> Dict[str, str]:
    data["ctl00$MainContent$txtID"] = AMBASSY_REQUEST_NUMBER
    data["ctl00$MainContent$txtUniqueID"] = AMBASSY_PROTECTION_CODE
    data["ctl00$MainContent$txtCode"] = solve_captcha(captcha_image)
    data["ctl00$MainContent$FeedbackClientID"] = "0"
    data["ctl00$MainContent$FeedbackOrderID"] = "0"
    return data

def submit_filled_form(url: str, form_data: Dict[str, str]) -> bytes:
    response = http_req(url, form_data)
    ERR_MSG = "Символы с картинки введены неправильно".encode("utf-8")
    if ERR_MSG in response:
        raise CaptchaSolvingError("Captcha was not solved correctly")
    return response

def submit_second_form(url: str, first_form_results: bytes) -> str:
    soup0 = BeautifulSoup(first_form_results, "html.parser")
    second_form_data = extract_soup_form_data(soup0)
    second_form_data["ctl00$MainContent$ButtonB.x"] = "0"
    second_form_data["ctl00$MainContent$ButtonB.y"] = "0"
    logger.debug("Second form data: %s", second_form_data)
    soup = get_soup(url, second_form_data)
    center_panel = soup.find(id="center-panel")
    if not center_panel:
        raise ValueError("No center panel found")
    return center_panel.get_text()

def chain_all_requests():
    url = f"https://{AMBASSY_CITY}.kdmid.ru/queue/OrderInfo.aspx?id={AMBASSY_REQUEST_NUMBER}&cd={AMBASSY_PROTECTION_CODE}"
    soup = get_soup(url)
    logger.info("Extracting form data and captcha image...")

    form_data = extract_soup_form_data(soup)
    logger.debug(form_data)

    image_data = extract_image_data_by_id(soup, url)
    logger.info("Captcha image extracted. Solving...")

    form_data = fill_form_data(form_data, image_data)
    logger.info("Filled form data in first form. Submitting...")
    logger.debug(form_data)

    first_form_result = submit_filled_form(url, form_data)
    logger.info("First form submitted. Extracting calendar message...")

    message = submit_second_form(url, first_form_result)
    logger.info("Calendar message: " + message)

def main(*args, **kwargs):
    logger.info("Starting")
    logger.debug("args: %s, kwargs: %s", args, kwargs)
    for i in range(RETRY_COUNT):
        logger.info("Attempt %d", i+1)
        try:
            chain_all_requests()
            break
        except CaptchaSolvingError as e:
            logger.warning("Captcha solving error: %s", e)
            time.sleep(5)
            cookies.cookiejar.clear()
    logger.info("Done")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

