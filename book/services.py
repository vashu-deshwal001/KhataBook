from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import AuditLog, Customer, LedgerEntry


@transaction.atomic
def post_entry(*, actor, customer, kind, amount, date, submission_id, notes='', product=None, receipt=None):
    if not actor.is_shopkeeper:
        raise ValidationError('Only the shopkeeper can record transactions.')
    Customer.objects.select_for_update().get(pk=customer.pk)
    existing = LedgerEntry.objects.filter(submission_id=submission_id).first()
    if existing:
        if existing.customer_id != customer.pk:
            raise ValidationError('This submission has already been used.')
        return existing, False
    if kind not in {'purchase', 'payment', 'opening', 'advance'}:
        raise ValidationError('Invalid entry type.')
    if not customer.user.is_active:
        raise ValidationError('Activate this customer before adding transactions.')
    if date > timezone.localdate():
        raise ValidationError('Future dates are not allowed.')
    if kind in {'opening', 'advance'} and customer.entries.exists():
        raise ValidationError('An opening balance must be the first entry for a customer.')
    entry = LedgerEntry(customer=customer, kind=kind, amount=amount,
                        signed_amount=-amount if kind in {'payment', 'advance'} else amount,
                        date=date, submission_id=submission_id, notes=notes, product=product,
                        receipt=receipt or '', created_by=actor)
    entry.full_clean()
    entry.save()
    AuditLog.objects.create(actor=actor, action=f'Recorded entry #{entry.pk} for {customer.code}')
    return entry, True


@transaction.atomic
def reverse_entry(entry, actor, reason):
    if not actor.is_shopkeeper:
        raise ValidationError('Only the shopkeeper can reverse transactions.')
    entry = LedgerEntry.objects.select_for_update().get(pk=entry.pk)
    if entry.kind == 'reversal' or hasattr(entry, 'reversal'):
        raise ValidationError('This entry cannot be reversed again.')
    if not reason.strip():
        raise ValidationError('Enter a reason for the reversal.')
    reversal = LedgerEntry.objects.create(customer=entry.customer, kind='reversal', amount=entry.amount,
        signed_amount=-entry.signed_amount, date=timezone.localdate(), notes=reason.strip(),
        reversed_entry=entry, created_by=actor)
    AuditLog.objects.create(actor=actor, action=f'Reversed entry #{entry.pk}: {reason[:140]}')
    return reversal


@transaction.atomic
def edit_amount(entry, actor, amount, notes):
    if not actor.is_shopkeeper:
        raise ValidationError('Only the shopkeeper can modify amounts.')
    entry = LedgerEntry.objects.select_for_update().get(pk=entry.pk)
    if entry.kind == 'reversal' or hasattr(entry, 'reversal'):
        raise ValidationError('Reversed entries cannot be edited. Record a new transaction instead.')
    old_amount = entry.amount
    entry.amount = amount
    entry.signed_amount = -amount if entry.kind in {'payment', 'advance'} else amount
    entry.notes = notes
    entry.full_clean()
    entry.save(update_fields=['amount', 'signed_amount', 'notes'])
    AuditLog.objects.create(actor=actor, action=f'Edited entry #{entry.pk}: {old_amount} to {amount}')
    return entry


@transaction.atomic
def delete_entry(entry, actor):
    if not actor.is_shopkeeper:
        raise ValidationError('Only the shopkeeper can delete transactions.')
    entry = LedgerEntry.objects.select_for_update().get(pk=entry.pk)
    if entry.kind == 'reversal':
        raise ValidationError('Delete the original transaction to remove it and its reversal together.')
    AuditLog.objects.create(actor=actor, action=f'Deleted entry #{entry.pk}: {entry.kind} {entry.amount} for {entry.customer.code}')
    LedgerEntry.objects.filter(reversed_entry=entry).delete()
    entry.delete()


@transaction.atomic
def delete_customer(customer, actor):
    if not actor.is_shopkeeper:
        raise ValidationError('Only the shopkeeper can delete customer accounts.')
    customer = Customer.objects.select_for_update().select_related('user').get(pk=customer.pk)
    if customer.user.is_shopkeeper:
        raise ValidationError('The shopkeeper account cannot be deleted here.')
    user = customer.user
    AuditLog.objects.create(actor=actor, action=f'Deleted customer {customer.code} ({user.username}) and their ledger')
    customer.entries.update(reversed_entry=None)
    customer.entries.all().delete()
    customer.delete()
    user.delete()
