import type { ReactNode } from 'react';
export default function RootLayout({children}:{children:ReactNode}) {return <html lang="ja"><body style={{fontFamily:'sans-serif',maxWidth:850,margin:'40px auto',padding:16}}>{children}</body></html>}
