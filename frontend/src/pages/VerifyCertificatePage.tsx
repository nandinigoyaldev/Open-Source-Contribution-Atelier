import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchApi } from "../lib/api";
import { CheckCircle, XCircle, Award, Calendar, User, Hash, ArrowLeft } from "lucide-react";

interface CertificateData {
  verification_hash: string;
  course_name: string;
  issued_at: string;
  learner_name: string;
}

export function VerifyCertificatePage() {
  const { hash } = useParams<{ hash: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [data, setData] = useState<CertificateData | null>(null);

  useEffect(() => {
    const verifyHash = async () => {
      try {
        const response = await fetchApi(`/progress/verify/${hash}/`, {
          method: "GET",
          requireAuth: false,
        });
        if (response.is_valid && response.certificate) {
          setData(response.certificate);
        } else {
          setError("Invalid certificate response format.");
        }
      } catch (err: any) {
        setError(err.message || "Certificate Not Found or Invalid Hash.");
      } finally {
        setLoading(false);
      }
    };

    if (hash) verifyHash();
  }, [hash]);

  if (loading) {
    return (
      <div className="min-h-screen bg-bg flex flex-col items-center justify-center p-6">
        <div className="animate-pulse flex flex-col items-center gap-4">
          <div className="h-16 w-16 bg-muted rounded-full"></div>
          <div className="h-6 w-48 bg-muted rounded-xl"></div>
          <p className="text-black font-bold">Verifying Certificate...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg py-12 px-6 sm:px-12 flex flex-col items-center">
      <div className="w-full max-w-3xl mb-8 flex items-center justify-between">
        <Link
          to="/"
          className="group flex items-center gap-2 font-bold text-black border-4 border-black bg-white px-4 py-2 rounded-xl shadow-card-sm transition-all hover:-translate-y-1 hover:shadow-card active:translate-y-0 active:shadow-none"
        >
          <ArrowLeft className="h-5 w-5 transition-transform group-hover:-translate-x-1" strokeWidth={3} />
          Back Home
        </Link>
        <div className="text-xl font-black uppercase tracking-widest text-black">
          Contribution Atelier
        </div>
      </div>

      <div className="w-full max-w-3xl bg-white border-4 border-black rounded-3xl p-8 sm:p-12 shadow-card">
        {error || !data ? (
          <div className="flex flex-col items-center text-center space-y-6">
            <XCircle className="h-24 w-24 text-red-500" strokeWidth={2} />
            <h1 className="text-4xl font-black text-black uppercase">Invalid Certificate</h1>
            <p className="text-lg font-bold text-muted">
              We couldn't verify this certificate. The hash might be incorrect, expired, or tampered with.
            </p>
            <div className="bg-red-50 border-4 border-red-500 rounded-2xl p-4 w-full max-w-md">
              <span className="font-bold text-red-700 break-all">Hash: {hash}</span>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center space-y-10">
            <div className="flex flex-col items-center gap-2">
              <CheckCircle className="h-24 w-24 text-green-500" strokeWidth={2.5} />
              <h1 className="text-4xl font-black text-black uppercase tracking-tight text-center">
                Verified Certificate
              </h1>
              <div className="bg-green-100 text-green-800 font-bold px-4 py-1 rounded-full uppercase text-sm border-2 border-green-500 tracking-wider">
                Official Record
              </div>
            </div>

            <div className="w-full space-y-6">
              {/* Learner Name */}
              <div className="bg-surface-low border-4 border-black rounded-2xl p-6 shadow-card-sm flex items-start gap-4">
                <div className="bg-primary p-3 rounded-xl border-2 border-black">
                  <User className="h-6 w-6 text-black" strokeWidth={2.5} />
                </div>
                <div>
                  <p className="text-sm font-bold text-muted uppercase tracking-wide">Issued To</p>
                  <p className="text-2xl font-black text-black">{data.learner_name}</p>
                </div>
              </div>

              {/* Course Name */}
              <div className="bg-surface-low border-4 border-black rounded-2xl p-6 shadow-card-sm flex items-start gap-4">
                <div className="bg-accent p-3 rounded-xl border-2 border-black">
                  <Award className="h-6 w-6 text-black" strokeWidth={2.5} />
                </div>
                <div>
                  <p className="text-sm font-bold text-muted uppercase tracking-wide">For Completion Of</p>
                  <p className="text-2xl font-black text-black">{data.course_name}</p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                {/* Date Issued */}
                <div className="bg-surface-low border-4 border-black rounded-2xl p-6 shadow-card-sm flex items-start gap-4">
                  <div className="bg-tertiary p-3 rounded-xl border-2 border-black">
                    <Calendar className="h-6 w-6 text-black" strokeWidth={2.5} />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-muted uppercase tracking-wide">Issue Date</p>
                    <p className="text-lg font-black text-black">
                      {new Date(data.issued_at).toLocaleDateString(undefined, {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric'
                      })}
                    </p>
                  </div>
                </div>

                {/* Hash */}
                <div className="bg-surface-low border-4 border-black rounded-2xl p-6 shadow-card-sm flex items-start gap-4">
                  <div className="bg-yellow-300 p-3 rounded-xl border-2 border-black">
                    <Hash className="h-6 w-6 text-black" strokeWidth={2.5} />
                  </div>
                  <div className="overflow-hidden">
                    <p className="text-sm font-bold text-muted uppercase tracking-wide">Verification Hash</p>
                    <p className="text-sm font-black text-black truncate" title={data.verification_hash}>
                      {data.verification_hash}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
