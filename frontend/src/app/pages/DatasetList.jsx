import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getDatasets } from '../../lib/api';
import { PlusIcon, DocumentIcon, CalendarIcon } from '@heroicons/react/24/outline';

export default function DatasetList() {
    const [datasets, setDatasets] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        loadDatasets();
    }, []);

    const loadDatasets = async () => {
        try {
            const data = await getDatasets();
            setDatasets(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    if (loading) return <div className="p-8 text-center text-gray-500">Loading datasets...</div>;

    return (
        <div>
            <div className="flex justify-between items-center mb-8">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Datasets</h1>
                    <p className="text-sm text-gray-500 mt-1">Manage your clinical data files</p>
                </div>
                <Link
                    to="/upload"
                    className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition shadow-sm font-medium text-sm"
                >
                    <PlusIcon className="w-5 h-5" />
                    <span>Upload New</span>
                </Link>
            </div>

            {error && (
                <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-600 rounded-lg text-sm">
                    {error}
                </div>
            )}

            {datasets.length === 0 ? (
                <div className="text-center py-20 bg-white rounded-xl border border-dashed border-gray-300">
                    <DocumentIcon className="w-12 h-12 mx-auto text-gray-300 mb-3" />
                    <h3 className="text-lg font-medium text-gray-900">No datasets yet</h3>
                    <p className="text-gray-500 mb-6">Upload your first dataset to get started</p>
                    <Link to="/upload" className="text-blue-600 font-medium hover:underline">
                        Upload a file &rarr;
                    </Link>
                </div>
            ) : (
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                    <table className="w-full text-left text-sm">
                        <thead className="bg-gray-50 border-b border-gray-100 text-xs uppercase text-gray-500 font-semibold">
                            <tr>
                                <th className="px-6 py-4">Filename</th>
                                <th className="px-6 py-4">ID</th>
                                <th className="px-6 py-4">Uploaded</th>
                                <th className="px-6 py-4 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {datasets.map((ds) => (
                                <tr key={ds.id} className="hover:bg-gray-50 transition">
                                    <td className="px-6 py-4 font-medium text-gray-900 flex items-center space-x-3">
                                        <div className="w-8 h-8 rounded bg-blue-50 text-blue-600 flex items-center justify-center">
                                            <DocumentIcon className="w-4 h-4" />
                                        </div>
                                        <span>{ds.filename}</span>
                                    </td>
                                    <td className="px-6 py-4 text-gray-500 font-mono text-xs">{ds.id.substring(0, 8)}...</td>
                                    <td className="px-6 py-4 text-gray-500 flex items-center space-x-2">
                                        <CalendarIcon className="w-4 h-4 text-gray-400" />
                                        <span>Today</span> {/* Mock date for now */}
                                    </td>
                                    <td className="px-6 py-4 text-right space-x-4">
                                        <Link
                                            to={`/analyze/${ds.id}`}
                                            className="text-blue-600 hover:text-blue-800 font-medium"
                                        >
                                            Analyze
                                        </Link>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
