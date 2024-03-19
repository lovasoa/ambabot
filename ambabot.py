import ssl
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
import os
from typing import Dict, Optional
import boto3
from urllib.parse import urlencode
import logging
import time
from typing import Optional, Dict

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
AMBASSY_REQUEST_NUMBER = os.environ["AMBASSY_REQUEST_NUMBER"]
AMBASSY_PROTECTION_CODE = os.environ["AMBASSY_PROTECTION_CODE"]
RETRY_COUNT = int(os.environ.get("RETRY_COUNT", "3"))
EMAIL_FROM = os.getenv("EMAIL_FROM", "contact@ophir.dev")
EMAIL_TO = os.getenv("EMAIL_TO", "contact@ophir.dev")


logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

cookies = urllib.request.HTTPCookieProcessor()
ssl_ctx = ssl.create_default_context()
# The server closes the connection if we use the default cipher suite
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
    # Find the image element by its ID
    image_id = "ctl00_MainContent_imgSecNum"
    img = soup.find(id=image_id)
    if not img:
        raise ValueError(f"No image found with ID '{image_id}'")
    src: str = img.get("src")
    if not src:
        raise ValueError(
            f"No 'src' attribute found for image with ID '{image_id}'")
    # Resolve the relative URL to an absolute one (same folder as the page URL)
    src = "/".join(url.split("/")[:-1] + [src])
    # download the image
    image_bytes = http_req(src)
    return image_bytes


def extract_soup_form_data(soup: BeautifulSoup) -> Dict[str, str]:
    """Extract all form data from the given BeautifulSoup object."""
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


def solve_captcha(image: bytes) -> str:
    """Solve the captcha using the given image, using AWS textract """
    client = boto3.client('textract')
    response = client.detect_document_text(
        Document={
            'Bytes': image
        }
    )
    # The text is in the "Text" field of the "WORD" block type
    for block in response["Blocks"]:
        if block["BlockType"] == "WORD":
            txt: str = block["Text"]
            # We are looking for a 6-character number-only string
            if txt.isdigit() and len(txt) == 6:
                return txt
    raise CaptchaSolvingError("No text found in the image: " + str(response))


def fill_form_data(data: Dict[str, str], captcha_image: bytes) -> Dict[str, str]:
    """Fill the form data with the given captcha image."""
    #  Номер заявки (ID)
    data["ctl00$MainContent$txtID"] = AMBASSY_REQUEST_NUMBER
    #  Защитный код
    data["ctl00$MainContent$txtUniqueID"] = AMBASSY_PROTECTION_CODE
    #  Капча
    data["ctl00$MainContent$txtCode"] = solve_captcha(captcha_image)
    data["ctl00$MainContent$FeedbackClientID"] = "0"
    data["ctl00$MainContent$FeedbackOrderID"] = "0"
    return data


def submit_filled_form(url: str, form_data: Dict[str, str]) -> bytes:
    # Submit the form
    response = http_req(url, form_data)
    ERR_MSG = "Символы с картинки введены неправильно".encode("utf-8")
    if ERR_MSG in response:
        raise CaptchaSolvingError("Captcha was not solved correctly")
    return response


def submit_second_form(url: str, first_form_results: bytes) -> str:
    """Extract the calendar message from the page"""
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


def email_final_message(message: str):
    if "нет свободного времени" in message.lower():
        logger.info("ambabot: No free slots found :'(")
    else:
        msg = "ambabot: Free slots found !!!"
        # send email with aws ses
        client = boto3.client('ses')
        response = client.send_email(
            Destination={'ToAddresses': [EMAIL_TO]},
            Message={
                'Body': {'Text': {'Charset': 'UTF-8', 'Data': message}},
                'Subject': {'Charset': 'UTF-8', 'Data': msg, },
            },
            Source=EMAIL_FROM,
        )
        logger.info("Email sent: %s", response)


def chain_all_requests():
    url = f"https://paris.kdmid.ru/queue/OrderInfo.aspx?id={AMBASSY_REQUEST_NUMBER}&cd={AMBASSY_PROTECTION_CODE}"

    soup = get_soup(url)
    logger.info("Extracting form data and captcha image...")

    # form data
    form_data = extract_soup_form_data(soup)

    logger.debug(form_data)

    # Raw jpeg image data
    image_data = extract_image_data_by_id(soup, url)

    logger.info("Captcha image extracted. Solving...")

    # Fill the form data with the captcha image
    form_data = fill_form_data(form_data, image_data)

    logger.info("Filled form data in first form. Submitting...")
    logger.debug(form_data)

    # Submit the form
    first_form_result = submit_filled_form(url, form_data)

    logger.info("First form submitted. Extracting calendar message...")

    # Extract the calendar message
    message = submit_second_form(url, first_form_result)
    logger.info("Calendar message: " + message)
    email_final_message(message)


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
    main()
