export const endpoints = {
  prepare: () => '/prepare',
  start: (taskId: string) => `/start/${taskId}`,
  tasks: () => '/tasks',
  history: () => '/history',
  delete: (taskId: string) => `/delete/${taskId}`,
  downloadFile: (taskId: string) => `/download_file/${taskId}`,
  downloadToken: (taskId: string) => `/download_token/${taskId}`,
  cancel: (taskId: string) => `/cancel/${taskId}`,
  search: () => '/search',
  suggestions: () => '/suggestions',
} as const;
