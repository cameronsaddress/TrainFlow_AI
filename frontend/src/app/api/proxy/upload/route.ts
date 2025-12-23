
import { NextRequest, NextResponse } from 'next/server';

// App Router Config
export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const maxDuration = 300; // 5 minutes

export async function POST(req: NextRequest) {
    try {
        // Backend URL (Internal Docker DNS)
        const BACKEND_URL = "http://backend:8000";
        const targetUrl = `${BACKEND_URL}/api/knowledge/upload`;

        console.log(`[Proxy] Forwarding upload to ${targetUrl}`);

        // Forward the request to the backend
        // We must preserve the Content-Type header (multipart/form-data boundary)
        const contentType = req.headers.get('content-type');

        // Convert ReadableStream to Blob/Buffer if needed, or just pass stream
        // fetch() in Node 18+ supports passing the request body stream directly
        const backendResponse = await fetch(targetUrl, {
            method: 'POST',
            headers: {
                'Content-Type': contentType || '',
                // Add auth headers if needed
            },
            body: req.body, // Duplex stream
            // @ts-ignore - 'duplex' is a valid option in Node fetch but TS might complain
            duplex: 'half',
        });

        if (!backendResponse.ok) {
            const errorText = await backendResponse.text();
            console.error(`[Proxy] Backend error: ${backendResponse.status} - ${errorText}`);
            return NextResponse.json({ error: `Backend error: ${backendResponse.statusText}` }, { status: backendResponse.status });
        }

        const data = await backendResponse.json();
        return NextResponse.json(data);

    } catch (error: any) {
        console.error("[Proxy] Upload proxy failed:", error);
        return NextResponse.json({ error: "Upload proxy failed: " + error.message }, { status: 500 });
    }
}
