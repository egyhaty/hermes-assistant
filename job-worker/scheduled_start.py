"""Prepare the existing signed-in browser; never imports or transfers cookies."""
def prepare_feed():
 from selenium import webdriver
 from selenium.webdriver.chrome.options import Options
 from selenium.webdriver.chrome.service import Service
 options=Options();options.debugger_address='127.0.0.1:9222';options.page_load_strategy='eager'
 driver=webdriver.Chrome(service=Service('/usr/bin/chromedriver'),options=options)
 try:
  driver.set_page_load_timeout(45)
  driver.get('https://www.linkedin.com/feed/')
 finally:driver.service.stop()
