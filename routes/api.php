<?php

use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| API Routes
|--------------------------------------------------------------------------
|
| Here is where you can register API routes for your application. These
| routes are loaded by the RouteServiceProvider and all of them will
| be assigned to the "api" middleware group. Make something great!
|
*/

Route::prefix('ticket')->group(function () {

    Route::prefix('list')->group(function () {
        Route::match(['get', 'post'], '/sources', "WeeklyScheduleController@sources")->name('sources');
        Route::match(['get', 'post'], '/destinations', "WeeklyScheduleController@destinations")->name('destinations');
        Route::match(['get', 'post'], '/terminals', "WeeklyScheduleController@terminals")->name('terminals');
    });

    Route::match(['get', 'post'],'/searches', "SearchController@index")->name('searches');

    Route::post('/reserve', 'ReserveController@store')->name("reserve_store");
    Route::post('/cancellation', 'ReserveController@cancellation')->name("reserve_cancellation");

    Route::post('/buy', 'BuyController@store')->name("buy_store");
    Route::post('/extradition', 'BuyController@extradition')->name("extradition");

    Route::post('/check', 'BuyController@check')->name("check");

});
