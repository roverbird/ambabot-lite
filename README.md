# Embassy Appointment Checker

This script automates the process of checking for available appointment slots at a Russian embassy (kdmid.ru). It performs the following tasks:

1. Sends an HTTP request to the embassy website (kdmid.ru) to retrieve a form.
2. Extracts captcha image from the retrieved form.
3. Solves the captcha using Optical Character Recognition (OCR).
4. Submits the form with the solved captcha.
5. Extracts the appointment availability message from the response.

## Prerequisites

- Python 3.6 or higher
- The following Python packages:
  - `easyocr`
  - `pillow`
  - `beautifulsoup4`
  - `python-dotenv`

## Installation

1. Clone this repository or download the script files.
2. Navigate to the project directory.
3. Install the required Python packages using `pip`:
    ```sh
    pip install easyocr pillow beautifulsoup4 python-dotenv
    ```

## Setup

1. Create a `.env` file in the root directory of your project with the following content:
    ```env
    # Номер заявки
    AMBASSY_REQUEST_NUMBER=your_request_number
    # Защитный код
    AMBASSY_PROTECTION_CODE=your_protection_code
    RETRY_COUNT=10
    AMBASSY_CITY=your_city
    ```

2. Ensure you have the appropriate permissions to access the embassy's website.

Make sure to create 'первечная запись' to get Защитный код and Номер заявки

## Usage

Run the script with the following command:
```sh
python ambabot_lite.py

