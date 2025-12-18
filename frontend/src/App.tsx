import React from 'react';
import { SessionProvider } from './contexts/SessionContext';
import { QABlocksProvider } from './contexts/QABlocksContext';
import { Layout } from './components/Layout';
import { QuestionInput } from './components/QuestionInput';
import { QABlockList } from './components/QABlockList';

function App() {
  return (
    <SessionProvider>
      <QABlocksProvider>
        <Layout>
          <div className="space-y-6">
            <QuestionInput />
            <QABlockList />
          </div>
        </Layout>
      </QABlocksProvider>
    </SessionProvider>
  );
}

export default App;

