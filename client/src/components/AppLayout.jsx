import React from 'react';

const AppLayout = ({ children}) => {
    return (
        <div className="flex flex-col h-screen">
            <div className="flex flex-1 overflow-hidden">

                {/* Contenido principal */}
                <main className={`flex-1 bg-gray-150 transition-all duration-300 overflow-y-auto`}>
                    {/* Contenido principal */}
                    <div>
                        {children}
                    </div>
                </main>
            </div>
        </div>
    );
};

export default AppLayout;