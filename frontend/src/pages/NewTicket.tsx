import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { TFunction } from 'i18next'
import { ApiError, NetworkError } from '../api/errors'
import {
  PRIORITIES,
  SUBJECT_MAX,
  createTicket,
  fetchCategories,
  type NewTicketInput,
  type Priority,
} from '../api/tickets'

const FIELD_CLASSES =
  'rounded-md border border-line bg-bg px-3 text-sm text-text placeholder:text-text-3 disabled:cursor-not-allowed disabled:opacity-60'

type Field = 'subject' | 'category' | 'priority' | 'description'
type FieldErrors = Partial<Record<Field, string>>

const FIELDS: readonly Field[] = ['subject', 'category', 'priority', 'description']

/** Error de un campo a partir del código de la API (`{campo: código}`). */
function fieldMessage(field: Field, code: string, t: TFunction): string {
  switch (code) {
    case 'max_length':
      return t('newTicket.errors.tooLong')
    case 'blank':
    case 'required':
    case 'null':
      return field === 'category' ? t('newTicket.errors.pickCategory') : t('newTicket.errors.blank')
    default:
      return t('newTicket.errors.invalid')
  }
}

export function NewTicket() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [subject, setSubject] = useState('')
  const [category, setCategory] = useState('')
  const [priority, setPriority] = useState<Priority>('medium')
  const [description, setDescription] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [failure, setFailure] = useState<string | null>(null)

  const categories = useQuery({
    queryKey: ['categories'],
    queryFn: ({ signal }) => fetchCategories(signal),
    staleTime: 5 * 60_000,
  })

  const create = useMutation({
    mutationFn: (input: NewTicketInput) => createTicket(input),
    onSuccess: (ticket) => {
      queryClient.setQueryData(['tickets', 'detail', ticket.code], ticket)
      void queryClient.invalidateQueries({ queryKey: ['tickets'] })
      void queryClient.invalidateQueries({ queryKey: ['metrics'] })
      void navigate(`/tickets/${encodeURIComponent(ticket.code)}`)
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 400) {
        const body = error.body as Record<string, unknown> | null
        const next: FieldErrors = {}
        for (const field of FIELDS) {
          const code = body?.[field]
          if (typeof code === 'string') next[field] = fieldMessage(field, code, t)
        }
        if (Object.keys(next).length > 0) {
          setErrors(next)
          setFailure(null)
          return
        }
      }
      setErrors({})
      if (error instanceof NetworkError) setFailure(t('errors.network'))
      else if (error instanceof ApiError && error.status === 403)
        setFailure(t('detail.errors.forbidden'))
      else setFailure(t('newTicket.errors.generic'))
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    const input = { subject: subject.trim(), description: description.trim() }
    const next: FieldErrors = {}
    if (!input.subject) next.subject = t('newTicket.errors.blank')
    if (!category) next.category = t('newTicket.errors.pickCategory')
    if (!input.description) next.description = t('newTicket.errors.blank')
    setErrors(next)
    setFailure(null)
    if (Object.keys(next).length > 0) return
    create.mutate({ ...input, category: Number(category), priority })
  }

  function errorProps(field: Field) {
    return errors[field]
      ? { 'aria-invalid': true as const, 'aria-describedby': `new-${field}-error` }
      : {}
  }

  function fieldError(field: Field) {
    const message = errors[field]
    if (!message) return null
    return (
      <p id={`new-${field}-error`} role="alert" className="text-xs font-medium text-prio-urgent">
        {message}
      </p>
    )
  }

  return (
    <section className="flex flex-col gap-4">
      <Link to="/tickets" className="text-sm font-semibold text-accent-text hover:underline">
        ← {t('detail.back')}
      </Link>
      <div className="flex flex-col gap-1">
        <h1 className="font-display text-3xl font-bold tracking-tight">{t('newTicket.title')}</h1>
        <p className="text-sm text-text-3">{t('newTicket.subtitle')}</p>
      </div>

      <form
        onSubmit={submit}
        noValidate
        className="flex max-w-2xl flex-col gap-5 rounded-2xl border border-line bg-surface p-5.5"
      >
        <div className="flex flex-col gap-1.5">
          <label htmlFor="new-subject" className="text-xs font-semibold text-text-2">
            {t('newTicket.subject')}
          </label>
          <input
            id="new-subject"
            type="text"
            value={subject}
            maxLength={SUBJECT_MAX}
            onChange={(event) => setSubject(event.target.value)}
            placeholder={t('newTicket.subjectPlaceholder')}
            className={`${FIELD_CLASSES} h-10.5`}
            {...errorProps('subject')}
          />
          {fieldError('subject')}
        </div>

        <div className="flex flex-wrap gap-4">
          <div className="flex basis-52 flex-[1_1_13rem] flex-col gap-1.5">
            <label htmlFor="new-category" className="text-xs font-semibold text-text-2">
              {t('newTicket.category')}
            </label>
            <select
              id="new-category"
              value={category}
              disabled={categories.isPending || categories.isError}
              onChange={(event) => setCategory(event.target.value)}
              className={`${FIELD_CLASSES} h-10.5`}
              {...errorProps('category')}
            >
              <option value="">
                {categories.isPending ? t('newTicket.loadingCategories') : t('newTicket.pick')}
              </option>
              {categories.data?.map((item) => (
                <option key={item.id} value={String(item.id)}>
                  {item.name}
                </option>
              ))}
            </select>
            {categories.isError && (
              <p role="alert" className="text-xs text-text-2">
                {t('newTicket.categoriesFailed')}{' '}
                <button
                  type="button"
                  onClick={() => void categories.refetch()}
                  className="font-semibold text-accent-text hover:underline"
                >
                  {t('tickets.retry')}
                </button>
              </p>
            )}
            {fieldError('category')}
          </div>

          <div className="flex basis-52 flex-[1_1_13rem] flex-col gap-1.5">
            <label htmlFor="new-priority" className="text-xs font-semibold text-text-2">
              {t('newTicket.priority')}
            </label>
            <select
              id="new-priority"
              value={priority}
              onChange={(event) => setPriority(event.target.value as Priority)}
              className={`${FIELD_CLASSES} h-10.5`}
              {...errorProps('priority')}
            >
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {t(`tickets.priority.${p}`)}
                </option>
              ))}
            </select>
            {fieldError('priority')}
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="new-description" className="text-xs font-semibold text-text-2">
            {t('newTicket.description')}
          </label>
          <textarea
            id="new-description"
            rows={6}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder={t('newTicket.descriptionPlaceholder')}
            className={`${FIELD_CLASSES} resize-y py-3 leading-normal`}
            {...errorProps('description')}
          />
          {fieldError('description')}
        </div>

        {failure && (
          <p role="alert" className="text-[0.8125rem] font-medium text-prio-urgent">
            {failure}
          </p>
        )}

        <div className="flex flex-wrap items-center justify-end gap-3">
          <Link
            to="/tickets"
            className="inline-flex h-10.5 items-center rounded-md border border-line px-4.5 text-sm font-semibold hover:bg-bg"
          >
            {t('newTicket.cancel')}
          </Link>
          <button
            type="submit"
            disabled={create.isPending}
            className="inline-flex h-10.5 items-center rounded-md bg-accent px-4.5 text-sm font-semibold text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {create.isPending ? t('newTicket.creating') : t('newTicket.submit')}
          </button>
        </div>
      </form>
    </section>
  )
}
