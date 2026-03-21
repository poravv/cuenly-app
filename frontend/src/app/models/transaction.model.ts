export interface TransactionHistoryItem {
  id: string;
  amount: number;
  currency: string;
  status: 'success' | 'failed' | 'pending';
  created_at: string;
  attempt_number: number;
  plan_name: string | null;
  reference: string | null;
  error_message: string | null;
}

export interface PaginatedTransactions {
  items: TransactionHistoryItem[];
  total: number;
  page: number;
  pages: number;
  limit: number;
}
