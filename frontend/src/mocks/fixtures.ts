import type {
  ConfirmFieldsPayload,
  DocumentUploadPayload,
  DraftDocumentRow,
  DraftFieldRow,
  DraftSummary,
  MallPickerPayload,
  QuickRepliesPayload,
  ReviewPayload,
  SuccessPayload,
  UiCard,
  VerificationPayload,
} from '../types/contracts'

const DOCUMENT_ROWS: DraftDocumentRow[] = [
  {
    doc_type: 'company_profile',
    label: 'Company Profile',
    required: true,
    uploaded: false,
    file_name: null,
    size_bytes: null,
  },
  {
    doc_type: 'brand_profile',
    label: 'Brand Profile',
    required: true,
    uploaded: false,
    file_name: null,
    size_bytes: null,
  },
  {
    doc_type: 'cr_certificate',
    label: 'CR certificate',
    required: false,
    uploaded: false,
    file_name: null,
    size_bytes: null,
  },
  {
    doc_type: 'vat_certificate',
    label: 'VAT certificate',
    required: false,
    uploaded: false,
    file_name: null,
    size_bytes: null,
  },
  {
    doc_type: 'national_id',
    label: 'National ID / Iqama',
    required: false,
    uploaded: false,
    file_name: null,
    size_bytes: null,
  },
  {
    doc_type: 'national_address',
    label: 'National Address',
    required: false,
    uploaded: false,
    file_name: null,
    size_bytes: null,
  },
  {
    doc_type: 'articles_of_association',
    label: 'Article of Association',
    required: false,
    uploaded: false,
    file_name: null,
    size_bytes: null,
  },
]

function emptyFieldRows(): DraftFieldRow[] {
  return [
    {
      key: 'cr_number',
      label: 'CR number',
      group: 'company',
      display: null,
      source: null,
      confirmed: false,
      required: false,
    },
    {
      key: 'company_name',
      label: 'Company name',
      group: 'company',
      display: null,
      source: null,
      confirmed: false,
      required: true,
    },
    {
      key: 'company_address',
      label: 'Company address',
      group: 'company',
      display: null,
      source: null,
      confirmed: false,
      required: true,
    },
    {
      key: 'brand_name_en',
      label: 'Brand name (EN)',
      group: 'brand',
      display: null,
      source: null,
      confirmed: false,
      required: true,
    },
    {
      key: 'brand_name_ar',
      label: 'Brand name (AR)',
      group: 'brand',
      display: null,
      source: null,
      confirmed: false,
      required: true,
    },
    {
      key: 'unit_type',
      label: 'Unit type',
      group: 'brand',
      display: null,
      source: null,
      confirmed: false,
      required: true,
    },
    {
      key: 'sales_category',
      label: 'Sales category',
      group: 'brand',
      display: null,
      source: null,
      confirmed: false,
      required: true,
    },
    {
      key: 'malls',
      label: 'Malls',
      group: 'space',
      display: null,
      source: null,
      confirmed: false,
      required: true,
    },
    {
      key: 'area',
      label: 'Area',
      group: 'space',
      display: '10 – 25,000 sqm',
      source: 'default',
      confirmed: true,
      required: false,
    },
    {
      key: 'rent',
      label: 'Rent',
      group: 'space',
      display: null,
      source: null,
      confirmed: true,
      required: false,
    },
    {
      key: 'lease',
      label: 'Lease period',
      group: 'space',
      display: null,
      source: null,
      confirmed: true,
      required: false,
    },
    {
      key: 'first_name',
      label: 'First name',
      group: 'contact',
      display: null,
      source: null,
      confirmed: false,
      required: true,
    },
    {
      key: 'last_name',
      label: 'Last name',
      group: 'contact',
      display: null,
      source: null,
      confirmed: false,
      required: true,
    },
    {
      key: 'email',
      label: 'Email',
      group: 'contact',
      display: null,
      source: null,
      confirmed: false,
      required: true,
    },
    {
      key: 'mobile',
      label: 'Mobile',
      group: 'contact',
      display: null,
      source: null,
      confirmed: false,
      required: true,
    },
  ]
}

export const draftEmpty: DraftSummary = {
  phase: 'gate',
  fields: emptyFieldRows(),
  documents: DOCUMENT_ROWS.map((row) => ({ ...row })),
  checks: {
    required_filled: 0,
    required_total: 11,
    unconfirmed: 0,
    email_verified: false,
    mobile_verified: false,
    contact_verified: false,
    required_docs_uploaded: 0,
    required_docs_total: 2,
    terms_accepted: false,
  },
  can_submit: false,
  changed_keys: [],
}

export const draftMidway: DraftSummary = {
  phase: 'collecting',
  fields: emptyFieldRows().map((row) => {
    if (row.key === 'cr_number') {
      return { ...row, display: '1010123456', source: 'user', confirmed: true }
    }
    if (row.key === 'company_name') {
      return {
        ...row,
        display: 'Bean Street Trading Co.',
        source: 'verified',
        confirmed: false,
      }
    }
    if (row.key === 'company_address') {
      return {
        ...row,
        display: 'King Fahd Road, Al Olaya, Riyadh',
        source: 'verified',
        confirmed: false,
      }
    }
    if (row.key === 'brand_name_en') {
      return { ...row, display: 'Bean Street', source: 'user', confirmed: true }
    }
    if (row.key === 'brand_name_ar') {
      return { ...row, display: 'بين ستريت', source: 'derived', confirmed: false }
    }
    if (row.key === 'unit_type') {
      return { ...row, display: 'Specialty', source: 'derived', confirmed: false }
    }
    if (row.key === 'sales_category') {
      return { ...row, display: 'Food & Beverage · Café', source: 'derived', confirmed: false }
    }
    return row
  }),
  documents: DOCUMENT_ROWS.map((row) => ({ ...row })),
  checks: {
    required_filled: 4,
    required_total: 11,
    unconfirmed: 5,
    email_verified: false,
    mobile_verified: false,
    contact_verified: false,
    required_docs_uploaded: 0,
    required_docs_total: 2,
    terms_accepted: false,
  },
  can_submit: false,
  changed_keys: ['company_name', 'company_address'],
}

export const draftComplete: DraftSummary = {
  phase: 'review',
  fields: emptyFieldRows().map((row) => {
    const filled: Record<string, Partial<DraftFieldRow>> = {
      cr_number: { display: '1010123456', source: 'user', confirmed: true },
      company_name: { display: 'Bean Street Trading Co.', source: 'verified', confirmed: true },
      company_address: {
        display: 'King Fahd Road, Al Olaya, Riyadh',
        source: 'verified',
        confirmed: true,
      },
      brand_name_en: { display: 'Bean Street', source: 'user', confirmed: true },
      brand_name_ar: { display: 'بين ستريت', source: 'derived', confirmed: true },
      unit_type: { display: 'Specialty', source: 'derived', confirmed: true },
      sales_category: { display: 'Food & Beverage · Café', source: 'derived', confirmed: true },
      malls: {
        display: 'Riyadh Mall A, Riyadh Mall B',
        source: 'user',
        confirmed: true,
      },
      area: { display: '25 – 35 sqm', source: 'derived', confirmed: true },
      rent: { display: 'Up to SAR 250,000 / year', source: 'user', confirmed: true },
      lease: { display: '3 years', source: 'user', confirmed: true },
      first_name: { display: 'Ahmed', source: 'user', confirmed: true },
      last_name: { display: 'Al-Harbi', source: 'user', confirmed: true },
      email: { display: 'ahmed@beanstreet.sa', source: 'user', confirmed: true },
      mobile: { display: '+966 55 123 4567', source: 'user', confirmed: true },
    }
    const patch = filled[row.key]
    return patch ? { ...row, ...patch } : row
  }),
  documents: DOCUMENT_ROWS.map((row) => {
    if (row.doc_type === 'company_profile') {
      return {
        ...row,
        uploaded: true,
        file_name: 'BeanStreet_Company_Profile.pdf',
        size_bytes: 1_884_160,
      }
    }
    if (row.doc_type === 'brand_profile') {
      return {
        ...row,
        uploaded: true,
        file_name: 'BeanStreet_Brand_Deck.pdf',
        size_bytes: 3_355_443,
      }
    }
    return { ...row }
  }),
  checks: {
    required_filled: 11,
    required_total: 11,
    unconfirmed: 0,
    email_verified: true,
    mobile_verified: true,
    contact_verified: true,
    required_docs_uploaded: 2,
    required_docs_total: 2,
    terms_accepted: true,
  },
  can_submit: true,
  changed_keys: [],
}

export const confirmFieldsCardExample: UiCard = {
  card_id: 'confirm-1',
  card_type: 'confirm_fields',
  message_id: 'm_12',
  payload: {
    title: "Here's what your CR record shows. Is it still correct?",
    fields: [
      {
        key: 'cr_number',
        label: 'CR number',
        display: '1010123456',
        source: 'user',
        confirmed: true,
      },
      {
        key: 'company_name',
        label: 'Company name',
        display: 'Bean Street Trading Co.',
        source: 'verified',
        confirmed: false,
      },
      {
        key: 'company_address',
        label: 'Company address',
        display: 'King Fahd Road, Al Olaya, Riyadh',
        source: 'verified',
        confirmed: false,
      },
    ],
    all_confirmed: false,
  } satisfies ConfirmFieldsPayload,
}

export const mallPickerCardExample: UiCard = {
  card_id: 'malls',
  card_type: 'mall_picker',
  message_id: 'm_18',
  payload: {
    city: { id: 'riyadh', label: 'Riyadh' },
    malls: [
      { id: 'riyadh-mall-a', name: 'Riyadh Mall A' },
      { id: 'riyadh-mall-b', name: 'Riyadh Mall B' },
      { id: 'riyadh-mall-c', name: 'Riyadh Mall C' },
      { id: 'riyadh-mall-d', name: 'Riyadh Mall D' },
    ],
    selected: ['riyadh-mall-a'],
    min_select: 1,
    max_select: 1,
  } satisfies MallPickerPayload,
}

export const verificationCardExample: UiCard = {
  card_id: 'verification',
  card_type: 'verification',
  message_id: 'm_22',
  payload: {
    email: {
      masked: 'a***@beanstreet.sa',
      link_sent: true,
      verified: false,
      demo_token: 'demo-token',
    },
    mobile: {
      masked: '+96655****4567',
      code_sent: true,
      verified: false,
      attempts_left: 3,
      code_length: 4,
    },
    all_verified: false,
  } satisfies VerificationPayload,
}

export const documentUploadCardExample: UiCard = {
  card_id: 'documents',
  card_type: 'document_upload',
  message_id: 'm_26',
  payload: {
    docs: draftMidway.documents,
    required_uploaded: 0,
    required_total: 2,
    allowed_extensions: ['.doc', '.docx', '.jpg', '.jpeg', '.pdf', '.png', '.xlsx', '.zip'],
    max_mb: 5,
  } satisfies DocumentUploadPayload,
}

export const reviewCardExample: UiCard = {
  card_id: 'review',
  card_type: 'review',
  message_id: 'm_30',
  payload: {
    groups: [
      {
        title: 'Company',
        rows: draftComplete.fields
          .filter((f) => f.group === 'company')
          .map(({ key, label, display, source, confirmed, required }) => ({
            key,
            label,
            display,
            source,
            confirmed,
            required,
          })),
      },
      {
        title: 'Contact',
        rows: draftComplete.fields
          .filter((f) => f.group === 'contact')
          .map(({ key, label, display, source, confirmed, required }) => ({
            key,
            label,
            display,
            source,
            confirmed,
            required,
          })),
      },
    ],
    documents: draftComplete.documents,
    checks: draftComplete.checks,
    can_submit: false,
    terms_accepted: false,
    blockers: ['terms_not_accepted'],
  } satisfies ReviewPayload,
}

export const successCardExample: UiCard = {
  card_id: 'success',
  card_type: 'success',
  message_id: 'm_34',
  payload: {
    reference: 'GEO-SPC-482917',
    tracking_url: '/api/inquiries/GEO-SPC-482917',
    steps: [
      { label: 'Inquiry submitted', detail: 'Just now', state: 'done' },
      {
        label: 'Review',
        detail: 'Our team verifies your details and documents.',
        state: 'current',
      },
      {
        label: 'Sign in to Tenant Central',
        detail: 'After approval, with the email you registered.',
        state: 'upcoming',
      },
    ],
  } satisfies SuccessPayload,
}

export const quickRepliesCardExample: UiCard = {
  card_id: 'quick-replies',
  card_type: 'quick_replies',
  message_id: 'm_welcome',
  payload: {
    options: [
      { label: 'I have my CR number', text: 'I have my CR number' },
      { label: "I don't have it handy", text: "I don't have it handy" },
      {
        label: 'What do I need to get started?',
        text: 'What do I need to get started?',
      },
    ],
  } satisfies QuickRepliesPayload,
}
