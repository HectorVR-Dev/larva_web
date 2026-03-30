import React, { useState } from "react";
import AppLayout from './components/AppLayout';
import HorizontalNavbar from './components/horizontalNavbar/HorizontalNavbar';
import VerticalNavbar from './components/verticalNavbar/VerticalNavbar';

import WebRTCComponent from "./components/Webrtc/WebRTCComponent";
import ChatBot from "./components/chat";
import PageMain from "./components/pageMain/PageMain";


function App() {
    const [isNavbarVisible, setIsNavbarVisible] = useState(false);
    const [isChatVisible, setIsChatVisible] = useState(false);


    const handleToggleNavbar = () => {
        setIsNavbarVisible(!isNavbarVisible);
    };

    const handleToggleChat = () => {
        setIsChatVisible(!isChatVisible);
    };

    return (
        <AppLayout>

            {/* Navbar horizontal (fijo en la parte superior) */}
            <HorizontalNavbar handleToggleNavbar={handleToggleNavbar} handleToggleChat={handleToggleChat} isNavBarVisible={isNavbarVisible} isChatVisible={isChatVisible}>  
                <PageMain>
                    {/* Navbar vertical (desplegable) */}
                    <VerticalNavbar isVisible={isNavbarVisible} isChatVisible={isChatVisible} />

                    <WebRTCComponent isNavBarVisible={isNavbarVisible} isChatVisible={isChatVisible} />

                    <ChatBot isVisible={isChatVisible} isNavBarVisible={isNavbarVisible} /> 

                </PageMain>
            </HorizontalNavbar>
        </AppLayout>
    );
}

export default App;