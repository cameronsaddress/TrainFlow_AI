import { NextRequest, NextResponse } from 'next/server';

export const config = {
    matcher: ['/:path*'],
};

export function middleware(req: NextRequest) {
    const basicAuth = req.headers.get('authorization');

    if (basicAuth) {
        const authValue = basicAuth.split(' ')[1];
        const [user, pwd] = atob(authValue).split(':');

        // Credentials: trainflow_admin / coffee-mountain-signals
        if (user === 'trainflow_admin' && pwd === 'coffee-mountain-signals') {
            return NextResponse.next();
        }
    }

    // Allow Local API (Internal Search)
    if (req.nextUrl.pathname.startsWith('/local-api')) {
        return NextResponse.next();
    }

    const url = req.nextUrl;
    url.pathname = '/api/auth';

    return new NextResponse('Auth Required.', {
        status: 401,
        headers: {
            'WWW-Authenticate': 'Basic realm="Secure Area"',
        },
    });
}
