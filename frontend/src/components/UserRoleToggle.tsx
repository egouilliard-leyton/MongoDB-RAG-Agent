import React from 'react';
import { useSession } from '../contexts/SessionContext';

export const UserRoleToggle: React.FC = () => {
  const { userRole, updateUserRole } = useSession();

  return (
    <div className="flex items-center space-x-4">
      <span className="text-sm font-medium text-gray-700">Role:</span>
      <div className="flex bg-gray-100 rounded-lg p-1">
        <button
          onClick={() => updateUserRole('junior')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            userRole === 'junior'
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          Junior
        </button>
        <button
          onClick={() => updateUserRole('senior')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            userRole === 'senior'
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          Senior
        </button>
      </div>
      <span
        className={`text-xs px-2 py-1 rounded-full ${
          userRole === 'senior'
            ? 'bg-blue-100 text-blue-800'
            : 'bg-gray-100 text-gray-800'
        }`}
      >
        {userRole === 'senior' ? 'Can edit & save' : 'View only'}
      </span>
    </div>
  );
};

