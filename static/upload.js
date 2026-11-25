document.querySelectorAll('[data-receipt-upload]').forEach((container) => {
  const input = container.querySelector('input[type="file"]');
  const name = container.querySelector('[data-upload-name]');
  const browse = container.querySelector('.upload-browse');
  const initialName = name.textContent;
  const update = () => {
    const file = input.files[0];
    name.textContent = file ? file.name : initialName;
    browse.textContent = file ? 'Change file' : 'Browse files';
    container.classList.toggle('has-file', Boolean(file));
  };
  input.addEventListener('change', update);
  if (input.form) input.form.addEventListener('reset', () => setTimeout(update, 0));
  container.classList.add('upload-ready');
  update();
});
