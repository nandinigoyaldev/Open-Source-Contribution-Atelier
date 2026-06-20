import React, { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { fetchApi } from "../lib/api";
import { CheckCircle, XCircle, Award, Calendar, User, Hash, ArrowLeft, Search, AlertOctagon } from "lucide-react";

interface CertificateData {
  verification_hash: string;
  course_name: string;
  issued_at: string;
  learner_name: string;
  is_active?: boolean;
}

export function VerifyCertificatePage() {
  const { hash } = useParams<{ hash: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState<CertificateData | null>(null);
  const [searchHash, setSearchHash] = useState("");

  useEffect(() => {
    const verifyHash = async () => {
      setLoading(true);
      setError("");
      setData(null);
      try {
        const response = await fetchApi(`/progress/verify/${hash}/`, {
          method: "GET",
          requireAuth: false,
        });
        if (response.certificate) {
          setData(response.certificate);
          if (!response.is_valid) {
            setError(response.error || "This certificate has been revoked or deactivated.");
          }
        } else {
          setError("Invalid certificate response format.");
        }
      } catch (err: any) {
        setError(err.message || "Certificate Not Found or Invalid Hash.");
      } finally {
        setLoading(false);
      }
    };

    if (hash) {
      verifyHash();
    } else {
      setLoading(false);
      setError("");
      setData(null);
    }
  }, [hash]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanHash = searchHash.trim();
    if (!cleanHash) {
      setError("Please enter a certificate hash to search.");
      return;
    }
    navigate(`/verify/${cleanHash}`);
  };

  // 1. Loading State
  if (loading) {
    return (
      <div className="min-h-screen bg-bg flex flex-col items-center justify-center p-6">
        <div className="animate-pulse flex flex-col items-center gap-4">
          <div className="h-16 w-16 bg-muted rounded-full animate-spin"></div>
          <div className="h-6 w-48 bg-muted rounded-xl"></div>
          <p className="text-black font-bold">Verifying Certificate...</p>
        </div>
      </div>
    );
  }

  // 2. Portal Lookup page (no hash provided)
  if (!hash) {
    return (
      <div className="min-h-screen bg-bg py-12 px-6 sm:px-12 flex flex-col items-center">
        <div className="w-full max-w-3xl mb-8 flex items-center justify-between no-print">
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

        <div className="w-full max-w-3xl bg-white border-4 border-black rounded-3xl p-8 sm:p-12 shadow-card relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 text-7xl opacity-10 pointer-events-none select-none">
            🎓
          </div>
          
          <div className="flex flex-col items-center text-center space-y-6">
            <Award className="h-20 w-20 text-primary" strokeWidth={2} />
            <h1 className="text-4xl font-black text-black uppercase tracking-tight">
              Certificate Verification
            </h1>
            <p className="text-lg font-bold text-muted max-w-xl">
              Verify the authenticity of graduation credentials issued by the Open Source Contribution Atelier. Enter a certificate verification hash below.
            </p>

            <form onSubmit={handleSearchSubmit} className="w-full max-w-lg mt-6 space-y-4">
              <div className="flex flex-col sm:flex-row gap-4">
                <div className="relative flex-grow">
                  <Hash className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted" />
                  <input
                    type="text"
                    placeholder="Enter Certificate Hash..."
                    value={searchHash}
                    onChange={(e) => setSearchHash(e.target.value)}
                    className="w-full pl-12 pr-4 py-4 bg-white border-4 border-black rounded-2xl font-bold text-black placeholder-muted/65 focus:outline-none focus:ring-0 focus:border-primary shadow-card-sm transition-all"
                  />
                </div>
                <button
                  type="submit"
                  className="flex items-center justify-center gap-2 px-6 py-4 bg-accent text-black font-black border-4 border-black rounded-2xl shadow-card-sm transition-all hover:-translate-y-1 hover:shadow-card active:translate-y-0 active:shadow-none whitespace-nowrap"
                >
                  <Search className="h-5 w-5" strokeWidth={3} />
                  Verify
                </button>
              </div>
              {error && (
                <div className="text-red-500 font-bold text-sm text-left px-2">
                  ⚠️ {error}
                </div>
              )}
            </form>
          </div>
        </div>
      </div>
    );
  }

  // 3. Hash verification results page
  return (
    <div className="min-h-screen bg-bg py-12 px-6 sm:px-12 flex flex-col items-center">
      <div className="w-full max-w-3xl mb-8 flex items-center justify-between">
        <Link
          to="/verify"
          className="group flex items-center gap-2 font-bold text-black border-4 border-black bg-white px-4 py-2 rounded-xl shadow-card-sm transition-all hover:-translate-y-1 hover:shadow-card active:translate-y-0 active:shadow-none"
        >
          <ArrowLeft className="h-5 w-5 transition-transform group-hover:-translate-x-1" strokeWidth={3} />
          New Search
        </Link>
        <div className="text-xl font-black uppercase tracking-widest text-black">
          Contribution Atelier
        </div>
      </div>

      <div className="w-full max-w-3xl bg-white border-4 border-black rounded-3xl p-8 sm:p-12 shadow-card certificate-printable">
        {error && !data ? (
          /* Case 3a: Non-existent hash (404 Error) */
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
        ) : data && data.is_active === false ? (
          /* Case 3b: Revoked/Inactive Certificate */
          <div className="flex flex-col items-center space-y-10">
            <div className="flex flex-col items-center gap-2">
              <AlertOctagon className="h-24 w-24 text-red-500 animate-bounce" strokeWidth={2} />
              <h1 className="text-4xl font-black text-black uppercase tracking-tight text-center">
                Revoked Certificate
              </h1>
              <div className="bg-red-100 text-red-800 font-bold px-4 py-1 rounded-full uppercase text-sm border-2 border-red-500 tracking-wider">
                Inactive Record
              </div>
            </div>

            <div className="w-full bg-red-50 border-4 border-red-500 rounded-2xl p-6 shadow-card-sm text-center">
              <p className="text-lg font-black text-red-700 uppercase mb-2">⚠️ Security Alert</p>
              <p className="font-bold text-red-600">
                {error || "This certificate has been explicitly revoked or deactivated by the maintainers."}
              </p>
            </div>

            <div className="w-full space-y-6 opacity-60">
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
        ) : data ? (
          /* Case 3c: Valid Certificate */
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
        ) : null}
      </div>
    </div>
  );
}
