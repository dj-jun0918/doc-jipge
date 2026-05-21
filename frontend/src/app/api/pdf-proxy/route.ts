import { NextResponse } from "next/server";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const pdfUrl = searchParams.get("url");

    if (!pdfUrl) {
      return NextResponse.json(
        { message: "url 파라미터가 누락되었습니다." },
        { status: 400 }
      );
    }

    // CORS 우회를 위해 외부 PDF 파일을 Fetch합니다.
    const response = await fetch(pdfUrl, {
      method: "GET",
    });

    if (!response.ok) {
      return NextResponse.json(
        { message: "PDF 파일을 다운로드할 수 없습니다." },
        { status: response.status }
      );
    }

    const arrayBuffer = await response.arrayBuffer();
    const headers = new Headers();
    headers.set("Content-Type", "application/pdf");
    headers.set("Content-Disposition", "inline");

    return new NextResponse(arrayBuffer, {
      status: 200,
      headers,
    });
  } catch (error) {
    console.error("PDF Proxy Route Handler Error:", error);
    return NextResponse.json(
      { message: "PDF 프록시 중 오류가 발생했습니다." },
      { status: 500 }
    );
  }
}
