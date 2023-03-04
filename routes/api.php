<?php

use App\Http\Controllers\BuyController;
use App\Http\Controllers\ReserveController;
use App\Http\Controllers\SearchController;
use App\Http\Controllers\WeeklyScheduleController;
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
        Route::match(['get', 'post'], '/sources', [WeeklyScheduleController::class, "index"])->name('sources');
        Route::match(['get', 'post'], '/destinations', [WeeklyScheduleController::class, "index"])->name('destinations');
        Route::match(['get', 'post'], '/terminals', [WeeklyScheduleController::class, "index"])->name('terminals');
    });

    Route::match(['get', 'post'],'/searches', [SearchController::class,"index"])->name('searches');

    Route::post('/reserve', [ReserveController::class, 'store'])->name("reserve_store");
    Route::post('/cancellation', [ReserveController::class, 'cancellation'])->name("reserve_cancellation");

    Route::post('/buy', [BuyController::class, 'store'])->name("buy_store");
    Route::post('/extradition', [BuyController::class, 'extradition'])->name("extradition");

    Route::post('/check', [BuyController::class, 'check'])->name("check");

});
