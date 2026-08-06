// TODO: create a second Formspree form for general inquiries and replace this endpoint.
const CONTACT_FORMSPREE_ENDPOINT = 'https://formspree.io/f/REPLACE_WITH_YOUR_CONTACT_FORM_ID';

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('contact-form');
  if (!form) return;
  const statusEl = document.getElementById('contact-status');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const submitBtn = form.querySelector('button[type="submit"]');
    const messageValue = form.message.value;
    submitBtn.disabled = true;
    statusEl.textContent = 'Sending your message...';
    statusEl.className = 'form-status';

    try {
      const res = await fetch(CONTACT_FORMSPREE_ENDPOINT, {
        method: 'POST',
        headers: { Accept: 'application/json' },
        body: new FormData(form)
      });
      if (!res.ok) throw new Error('Request failed');
      form.reset();
      form.hidden = true;
      statusEl.textContent = "Thanks for reaching out! We'll get back to you soon.";
      statusEl.className = 'form-status success';
    } catch (err) {
      console.error(err);
      const mailBody = encodeURIComponent(messageValue);
      statusEl.innerHTML = `Sorry, something went wrong sending your message. Please <a href="mailto:Em.r.mangos@gmail.com?subject=Website%20Inquiry&body=${mailBody}">email us directly</a> instead.`;
      statusEl.className = 'form-status error';
      submitBtn.disabled = false;
    }
  });
});
