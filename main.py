# The goal of this project is to simply find like query, go to openai.com and a few job websites that I'm interested in. Get all of the jobs and compare them to a local cache and if there is any new ones, see if they're relevant to me. If not, or if they are, then send me an email with them.
from nova_act import NovaAct

with NovaAct(starting_page="https://x.ai/careers/open-roles") as nova:
	nova.act("Return a list of all of the jobs title and links on this website. Stay on this page where we are searching for engineer and in san francisco")
