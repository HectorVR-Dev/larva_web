import React, { Children } from 'react';
import { FaBars } from 'react-icons/fa';
import { MdOutlineSpaceDashboard } from "react-icons/md";
import { MdOutlineSettings } from "react-icons/md";
import { LuUserRound } from "react-icons/lu";
import { LuMicroscope } from "react-icons/lu";
import { IoChatbubblesOutline } from "react-icons/io5";
import { IoReturnUpForwardOutline } from "react-icons/io5";
import { IoReturnUpBackOutline } from "react-icons/io5";



const HorizontalNavbar = ({ children, handleToggleNavbar, handleToggleChat, isNavBarVisible, isChatVisible }) => {
    const hoverClasses = [
        'hover:text-white',
        'hover:bg-blue-900',
        'hover:shadow-lg',
        'transition-transform duration-200 ease-in-out',
        'hover:scale-105',
        'active:scale-95',
        'rounded',
        'p-2',
        'block',
    ].join(' ');



    return (
        <div className="fixed top-0 left-0 w-full z-50 ">
            <div className="bg-blue-800 justify-center align-middle p-4 gap-4 top-0 left-0 w-full z-10 shadow-md flex">
                {/* Botón Menu*/}
                <button
                    onClick={handleToggleNavbar}
                    className={`bg-blue-800 text-white p-2 rounded-full hover:bg-blue-900 transition-transform duration-200 ease-in-out hover:scale-110 active:scale-95 ${(isNavBarVisible || isChatVisible) ? "hidden" : "block"} sm:block`}
                >
                    <FaBars className="text-xl" />
                </button>
                {/* Botón retorno - Chat / Interface Móvil */}
                <button
                    onClick={handleToggleChat}
                    className={`bg-blue-800 text-white p-2 rounded-full  hover:bg-blue-900 transition-transform duration-200 ease-in-out hover:scale-110 active:scale-95 ${(isChatVisible) ? "block" : "hidden" } sm:hidden`}
                >
                    <IoReturnUpBackOutline className="text-3xl" />
                </button>

                {/* Contenedor del título "Larva" */}
                <div className="w-full flex justify-center items-center  text-white">
                    <LuMicroscope className="text-3xl " />
                    <h2 className="text-2xl font-extrabold items-center gap-2 flex ml-2">
                        LARVA - IA
                    </h2>
                </div>

                {/* Botón Chat */}
                <button
                    onClick={handleToggleChat}
                    className={`bg-blue-800 text-white p-2 rounded-full  hover:bg-blue-900 transition-transform duration-200 ease-in-out hover:scale-110 active:scale-95 ${(isNavBarVisible || isChatVisible) ? "hidden" : "block"} sm:block`}
                >
                    <IoChatbubblesOutline className="text-3xl" />
                </button>

                {/* Botón retorno - Navbar / Interface Móvil */}
                <button
                    onClick={handleToggleNavbar}
                    className={`bg-blue-800 text-white p-2 rounded-full  hover:bg-blue-900 transition-transform duration-200 ease-in-out hover:scale-110 active:scale-95 ${(isNavBarVisible) ? "block" : "hidden" } sm:hidden`}
                >
                    <IoReturnUpForwardOutline className="text-3xl" />
                </button>
            </div>
            <div className='flex justify-evenly'>
                {children}
            </div>
        </div>

    );
};

export default HorizontalNavbar;