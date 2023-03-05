<?php

namespace App\Http\Controllers\API;

use App\Http\Controllers\Controller;
use App\Http\Requests\ListWeeklyScheduleRequest;
use App\Http\Requests\StoreWeeklyScheduleRequest;
use App\Models\WeeklySchedule;
use Illuminate\Http\Request;

class WeeklyScheduleController extends Controller
{
    /**
     * Display a listing of the resource.
     */
    public function index(ListWeeklyScheduleRequest $request)
    {
        $validate = $request->validated();
        $data = null;
        if($validate){
            switch ($request->input("actions")){
                case "terminals":
                    $data = WeeklySchedule::groupBy("source_city_id")->get();
                    break;
                case "destination":
                    $data = WeeklySchedule::groupBy("destination_city_id")->get();
                    break;
                case "source":
                    $data = WeeklySchedule::groupBy("source_terminal_id")->get();
                    break;
            }
            if ($data == null)
                return response("null", 404)->header('Content-Type', 'application/json');
            else
                return response()->json($data)->header('Content-Type', 'application/json');
        }
    }

    /**
     * Store a newly created resource in storage.
     */
    public function store(StoreWeeklyScheduleRequest $request)
    {
        $validate = $request->validated();

        if($validate){
            //todo save data.
        }
    }

    /**
     * Display the specified resource.
     */
    public function show(string $id)
    {
        //
    }

    /**
     * Update the specified resource in storage.
     */
    public function update(Request $request, string $id)
    {
        //
    }

    /**
     * Remove the specified resource from storage.
     */
    public function destroy(string $id)
    {
        //
    }
}
