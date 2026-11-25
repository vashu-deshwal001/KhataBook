(() => {
  const form = document.getElementById('transaction-form');
  const customers = JSON.parse(document.getElementById('customer-balances').textContent);
  const money = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' });
  // Convert decimal strings to integer paise for the preview calculation.
  const paise = (value) => {
    if (!/^-?\d+(\.\d{1,2})?$/.test(value)) return null;
    const [whole, fraction = ''] = value.replace('-', '').split('.');
    const result = Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
    return Number.isSafeInteger(result) ? (value.startsWith('-') ? -result : result) : null;
  };
  const set = (id, text) => { document.getElementById(id).textContent = text; };
  const update = () => {
    const customer = customers[form.elements.customer.value];
    const kind = form.elements.kind;
    const amount = paise(form.elements.amount.value.trim());
    const current = customer ? paise(customer.balance) : null;
    set('preview-name', customer ? customer.name : 'Select a customer');
    set('preview-code', customer ? customer.code : 'Their balance will appear here.');
    set('preview-current', current !== null ? money.format(current / 100) : '—');
    set('preview-type', kind.options[kind.selectedIndex].text);
    const valid = amount !== null && amount > 0 && form.elements.amount.validity.valid;
    const change = ['payment', 'advance'].includes(kind.value) ? -amount : amount;
    set('preview-change', valid ? `${change > 0 ? '+' : '−'} ${money.format(amount / 100)}` : '—');
    const total = current !== null && valid ? current + change : null;
    set('preview-total', total !== null ? money.format(total / 100) : '—');
    set('preview-status', total === null ? 'Choose a customer and enter an amount.' : total < 0 ? 'Customer has advance credit.' : total === 0 ? 'Account will be fully settled.' : 'Amount the customer will owe.');
  };
  form.addEventListener('input', update);
  form.addEventListener('change', update);
  update();
})();
