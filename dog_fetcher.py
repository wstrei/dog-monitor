import argparse
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import lxml.html
import os
import socket
import sys
import time
import traceback
import urllib.request

test='test'
DOGS_PAGE = 'https://www.animalhumanesociety.org/adoption?f%5B0%5D=animal_type%3ADog'
DOMAIN = 'https://www.animalhumanesociety.org'
PATH_TO_LINKS = '//div[@class="animal--image-wrapper"]//a'
PATH_TO_NAME = '//div[@class="animal-title"]//h1'
PATH_TO_BREED = '//div[@class="animal--breed"]'
PATH_TO_SEX = '//div[@class="animal--sex"]'
PATH_TO_AGE = '//div[@class="animal--age"]'
PATH_TO_WEIGHT = '//div[@class="animal--weight"]'
PATH_TO_LOCATION = '//div[@class="animal--location"]//div[@class="field__item"]'
PATH_TO_ID = '//div[@class="animal--details-bottom"]//div[@class="animal-item"]'
PATH_TO_IMG = '//div[@id="animal--main-image"]//img'

DELAY = 3600
SMTP_PORT = 587
SMTP_SERVER = 'smtp.gmail.com'
EMAIL_PASS = 'EMAIL_PASS'
TIMEOUT = 7

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%d %b %Y %H:%M')

"""
Builds a nicely formatted email body for a dog
"""
def build_email_body(dog):
	body = '<p>Name: {}</p><p>Breed: {}</p><p>Age: {}</p><p>Gender: {}</p><p>Link: {}</p><p>Location: {}</p><img src="cid:dog_img">'.format(dog['name'], dog['breed'], dog['age'], dog['gender'], dog['link'], dog['location'])
	return body

def create_recipient_list(recipients):
	recipient_list = ''
	for recipient in recipients:
		recipient_list += recipient + ','
	recipient_list.rstrip(',')
	return recipient_list

"""
Emails an alert that a new dog has been found
"""
def email_new_dogs(email_username, email_password, recipients, new_dogs):
	new_dog_count = 0
	for dog in new_dogs:
		# # Build email
		msg = MIMEMultipart()
		msg['Subject'] = 'New Dog at the Humane Society!'
		msg['From'] = email_username
		msg['To'] = create_recipient_list(recipients)
		msg.attach(MIMEText(build_email_body(dog), 'html'))

		# # Attach picture...
		img = MIMEImage(urllib.request.urlopen(dog['img']).read())
		img.add_header('Content-ID', '<dog_img>')
		msg.attach(img)

		# # Connect to SMTP server and send message
		smtp = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
		smtp.starttls()
		smtp.login(email_username, email_password)
		smtp.send_message(msg)
		smtp.quit()

		logging.info('Sent new dog email!')

"""
Returns the HTML page for all dog listings on the animal humane society website.
Will timeout after TIMEOUT seconds.
On any failure or non-200 response, returns None
"""
def get_dogs_page():
	try:
		response = urllib.request.urlopen(DOGS_PAGE, None, TIMEOUT)
		if response.status == 200:
			return response.read().decode('UTF-8')
		else:
			logging.error('Request failed with status ', response.status)
			return None
	except socket.timeout:
		logging.error('Request timed out :(...')
	except Exception as err:
		logging.error('Failed to get doggo page...')
		traceback.print_exception(type(err), err, sys.exc_info()[2])

	return None

"""
Given our current list of dogs, and the new list of dogs, check for any new dog,
and send email for any that are found
"""
def get_new_dogs(current_dogs, all_dogs):
	new_dogs = []
	for dog_hash in all_dogs:
		if dog_hash not in current_dogs:
			# We found a new pupper!
			logging.info('Found a new pupper!')
			new_dogs.append(all_dogs[dog_hash])
	return new_dogs

"""
Given the HTML of the dogs page, parse it to get a list of dogs
A dog is a dictionary of:
	name, age, breed, location, img
"""
def parse_dogs(dogs_html):
	all_dogs = {}
	main_doc = lxml.html.document_fromstring(dogs_html)
	dog_links = main_doc.xpath(PATH_TO_LINKS)
	
	logging.info('Parsing out the dogs...')
	count = 0
	for link in dog_links:
		full_link = DOMAIN + link.attrib['href']
		dog_page = urllib.request.urlopen(full_link)
		if dog_page.status == 200:
			html = dog_page.read().decode('UTF-8')
			dog_doc = lxml.html.document_fromstring(html)
			new_dog = {}

			# Get info from page
			new_dog['name'] = dog_doc.xpath(PATH_TO_NAME)[0].text_content()
			new_dog['breed'] = dog_doc.xpath(PATH_TO_BREED)[0].text_content()
			new_dog['age'] = dog_doc.xpath(PATH_TO_AGE)[0].text_content()
			new_dog['location'] = dog_doc.xpath(PATH_TO_LOCATION)[0].text_content()
			new_dog['link'] = full_link
			new_dog['img'] = dog_doc.xpath(PATH_TO_IMG)[0].attrib['src']
			dog_id = dog_doc.xpath(PATH_TO_ID)[0].text_content()

			# description = quick_view_doc.xpath('//*[contains(@class, "a_desq")]')
			# # If the details page is incomplete, just grab what should be there and fill the rest
			# if len(description) < 6:
			# 	new_dog['breed'] = 'check on site'
			# 	new_dog['gender'] = 'check on site'
			# 	new_dog['age'] = 'check on site'
			# 	new_dog['location'] = 'check on site'
			# 	new_dog['link'] = link
			# 	new_dog['img'] = DOMAIN + quick_view_doc.xpath('//img')[0].attrib['src']
			# 	dog_id_e = quick_view_doc.xpath('//*[contains(@class, "a_desq") and contains(text(), "ID")]')[0]
			# 	dog_id = dog_id_e.text_content().split(':')[-1]
			# else:
			# 	new_dog['breed'] = description[0].text_content()
			# 	new_dog['gender'] = description[1].text_content()
			# 	new_dog['age'] = description[2].text_content()
			# 	new_dog['location'] = description[5].text_content().split(':')[-1]
			# 	new_dog['img'] = DOMAIN + quick_view_doc.xpath('//img')[0].attrib['src']
			# 	new_dog['link'] = link
			# 	dog_id = int(description[4].text_content().split()[-1])
				
			all_dogs[dog_id] = new_dog
			count += 1
	logging.info('Finished parsing {} dogs'.format(count))
	return all_dogs

def watch_for_dogs(email_username, email_password, recipients):
	# Map of dog hashes to dogs. The hash is computed as hash(frozenset(dog.items())).
	current_dogs = {}

	# Let's watch for some doggies!
	logging.info('Watching for doggos!!')
	while(1):
		try:
			dogs_html = get_dogs_page()
			if dogs_html:
				# Get all the doggos currently there
				all_dogs = parse_dogs(dogs_html)
				# Look for any new dogs, but only if we haven't just started
				if current_dogs != {}:
					new_dogs = get_new_dogs(current_dogs, all_dogs)
					if len(new_dogs) > 0:
						email_new_dogs(email_username, email_password, recipients, new_dogs)

				# Set new list of current dogs
				current_dogs = all_dogs

		except Exception as err:
			logging.error('Failed becase ...')
			traceback.print_exception(type(err), err, sys.exc_info()[2])

		# Wait a bit before we check again
		time.sleep(DELAY)

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--sender_email_addr', help='Email address to send mail to', required=True)
	parser.add_argument('--recipients', help='List of addresses to send email to', nargs='+', required=True)
	parser.add_argument('--smtp_server', required=False)
	parser.add_argument('--smtp_port', type=int, required=False)
	parser.add_argument('--delay', type=int, required=False)
	args = parser.parse_args()

	# Process optional args
	if args.smtp_server:
		SMTP_SERVER = args.smtp_server
	if args.smtp_port:
		SMTP_PORT = args.smtp_port
	if args.delay:
		DELAY = args.delay

	# Get password from environment variable.
	# After this, parent process should remove password
	if EMAIL_PASS in os.environ:
		email_pass = os.environ[EMAIL_PASS]
	else:
		logging.error('No password in environment, so email is not possible.')
		logging.error('Exiting...')
		exit(1)

	watch_for_dogs(args.sender_email_addr, email_pass, args.recipients)
