const LABELS: Record<string, string> = {
  company_name: 'Company name',
  company_address: 'Address',
  brand_name_en: 'Brand name',
  brand_name_ar: 'Brand name (Arabic)',
  sales_category: 'Sales category',
}

export function labelFilledField(key: string): string {
  return LABELS[key] ?? key.replace(/_/g, ' ')
}

export function filledFieldsLine(keys: string[]): string {
  return keys.map(labelFilledField).join(', ')
}
